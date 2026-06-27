"""
PC 端代理中继服务器

把 NAS 的采集请求转发到你电脑上的 Clash 代理，从而通过 VPN 访问境外网站。

用法（你电脑上跑）：
  python proxy_server.py

默认监听 0.0.0.0:8888，转发到 Clash 的 127.0.0.1:7890。

如果 Clash 端口不同：
  python proxy_server.py --upstream http://127.0.0.1:7897

架构：
  ┌──────────┐       ┌───────────────────┐       ┌──────────┐       ┌──────────┐
  │ NAS 后端  │ ────→ │ proxy_server:8888 │ ────→ │ Clash    │ ────→ │ Google   │
  │ 172.18.1.20│      │ (你的电脑)         │       │127.0.0.1:7890│     │          │
  └──────────┘       └───────────────────┘       └──────────┘       └──────────┘

依赖：Python 3.8+，无需额外安装任何包
"""

import asyncio
import socket
import sys
import logging
import argparse
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("proxy")

HOST = "0.0.0.0"
PORT = 8888
BUFFER_SIZE = 65536


def get_lan_ip() -> str:
    """获取本机局域网 IP，排除回环地址"""
    # 方法1：UDP 连接 NAS 获取路由网卡 IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("172.18.1.20", 1))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass

    # 方法2：遍历所有网卡接口
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("172.") or ip.startswith("192.168.") or ip.startswith("10."):
                return ip
    except Exception:
        pass

    # 方法3：Google DNS 路由
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass

    return "127.0.0.1"


async def relay_via_proxy(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_url: str,
):
    """
    处理 HTTP 请求：从客户端读取完整请求，通过上游代理转发，
    然后将响应返回给客户端。

    支持 HTTP 和 HTTPS（通过 CONNECT 隧道）。
    """
    peer = client_writer.get_extra_info("peername", ("?", 0))
    parsed_upstream = urlparse(upstream_url)
    upstream_host = parsed_upstream.hostname
    upstream_port = parsed_upstream.port or 80

    try:
        # 读取请求行
        request_line = await asyncio.wait_for(
            client_reader.readuntil(b"\r\n"), timeout=10
        )
        method, url_or_path, _ = request_line.decode("utf-8", errors="replace").split(maxsplit=2)

        # 读取所有请求头
        headers = b""
        while True:
            line = await asyncio.wait_for(
                client_reader.readuntil(b"\r\n"), timeout=5
            )
            headers += line
            if line == b"\r\n":
                break

        if method == "CONNECT":
            # HTTPS 隧道
            target_host, target_port = url_or_path.split(":")
            target_port = int(target_port)

            logger.info(f"HTTPS → {target_host}:{target_port}")

            # 连接上游代理
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(upstream_host, upstream_port), timeout=5
            )

            # 发送 CONNECT 到上游
            connect_req = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\n\r\n"
            upstream_writer.write(connect_req.encode())
            await upstream_writer.drain()

            # 读取上游响应
            upstream_resp = await asyncio.wait_for(
                upstream_reader.readuntil(b"\r\n\r\n"), timeout=10
            )

            if b"200" not in upstream_resp.split(b"\r\n")[0]:
                logger.warning(f"上游代理拒绝 CONNECT: {upstream_resp.split(b'\r\n')[0].decode()}")
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await client_writer.drain()
                client_writer.close()
                return

            # 告诉客户端隧道已建立
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()

            # 双向透传
            async def pipe(src, dst, label):
                try:
                    while True:
                        chunk = await asyncio.wait_for(src.read(BUFFER_SIZE), timeout=120)
                        if not chunk:
                            break
                        dst.write(chunk)
                        await dst.drain()
                except Exception:
                    pass

            await asyncio.gather(
                pipe(client_reader, upstream_writer, "client→upstream"),
                pipe(upstream_reader, client_writer, "upstream→client"),
            )

        else:
            # HTTP 请求：通过上游代理转发
            # 重建完整 URL
            if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
                full_url = url_or_path
            else:
                # 从 Host 头获取
                host_header = ""
                for line in headers.decode("utf-8", errors="replace").split("\r\n"):
                    if line.lower().startswith("host:"):
                        host_header = line.split(":", 1)[1].strip()
                        break
                if host_header:
                    full_url = f"http://{host_header}{url_or_path}"
                else:
                    full_url = url_or_path

            logger.info(f"HTTP → {urlparse(full_url).hostname}")

            # 连接上游代理
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(upstream_host, upstream_port), timeout=5
            )

            # 重建请求（使用绝对 URL）
            new_req = f"{method} {full_url} HTTP/1.1\r\n".encode()
            upstream_writer.write(new_req)
            upstream_writer.write(headers)
            await upstream_writer.drain()

            # 如果有请求体，转发
            content_length = 0
            for line in headers.decode("utf-8", errors="replace").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_length = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                    break

            if content_length > 0:
                body = await asyncio.wait_for(
                    client_reader.readexactly(content_length), timeout=10
                )
                upstream_writer.write(body)
                await upstream_writer.drain()

            # 转发响应
            while True:
                chunk = await asyncio.wait_for(
                    upstream_reader.read(BUFFER_SIZE), timeout=30
                )
                if not chunk:
                    break
                client_writer.write(chunk)
                await client_writer.drain()

    except asyncio.TimeoutError:
        logger.debug(f"超时: {peer}")
    except ConnectionRefusedError:
        logger.error(f"Clash 代理 {upstream_host}:{upstream_port} 连接被拒绝，请确认 Clash 正在运行且端口正确")
    except Exception as e:
        logger.debug(f"错误: {peer} - {e}")
    finally:
        try:
            client_writer.close()
        except Exception:
            pass


async def handle_client(client_reader, client_writer, upstream_url: str):
    await relay_via_proxy(client_reader, client_writer, upstream_url)


async def main():
    parser = argparse.ArgumentParser(description="PC 端代理中继服务器")
    parser.add_argument(
        "--upstream",
        default="http://127.0.0.1:7890",
        help="上游代理地址（默认: http://127.0.0.1:7890，即 Clash HTTP 代理）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="本服务监听端口（默认: 8888）",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 8):
        logger.error("需要 Python 3.8+")
        return

    upstream_url = args.upstream
    port = args.port
    local_ip = get_lan_ip()

    # 测试到上游代理的连接
    parsed = urlparse(upstream_url)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(parsed.hostname, parsed.port or 80),
            timeout=3,
        )
        writer.close()
        upstream_ok = True
    except Exception as e:
        upstream_ok = False
        logger.error(f"无法连接到上游代理 {upstream_url}: {e}")
        logger.error("请确认 Clash 正在运行，且端口正确。")

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, upstream_url),
        HOST,
        port,
    )

    print()
    print("=" * 55)
    print("  PC 端代理中继服务器已启动")
    print("=" * 55)
    print(f"  监听地址:   {HOST}:{port}")
    print(f"  本机 IP:    {local_ip}")
    print(f"  上游代理:   {upstream_url} {'(已连接)' if upstream_ok else '(连接失败!)'}")
    print()
    print("  NAS 配置（docker-compose.yml 中 backend 的 environment）：")
    print(f"    - SCRAPER_PROXY_URL=http://{local_ip}:{port}")
    print()
    print("  ⚠️  确保电脑 VPN 已开启，且 Clash 正在运行")
    print("  按 Ctrl+C 停止")
    print("=" * 55)

    logger.info(f"代理中继启动: {HOST}:{port} → {upstream_url}")

    try:
        async with server:
            await server.serve_forever()
    except KeyboardInterrupt:
        print("\n代理服务器已停止")


if __name__ == "__main__":
    asyncio.run(main())