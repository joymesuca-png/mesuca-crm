"""
PC 端 HTTP 代理服务器

用于让 NAS 的采集引擎通过你电脑的 VPN 线路访问境外网站。

用法（在你电脑上运行）：
  python proxy_server.py

默认监听 0.0.0.0:8888，允许局域网内的 NAS 连接。

工作原理：
  ┌──────────┐       ┌──────────────┐       ┌──────────────┐
  │ NAS 后端  │ ────→ │ PC 代理 :8888 │ ────→ │ Google/Bing  │
  │ (无 VPN)  │       │  (有 VPN)     │       │  (境外)       │
  └──────────┘       └──────────────┘       └──────────────┘

依赖：Python 3.8+，无需额外安装任何包
"""

import asyncio
import socket
import ssl
import logging
import sys
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


async def handle_http(client_reader, client_writer, request_line: bytes):
    """处理 HTTP 请求（非加密）"""
    try:
        # 解析 GET http://example.com/path HTTP/1.1
        parts = request_line.split()
        if len(parts) < 2:
            return
        url = parts[1].decode("utf-8", errors="replace")
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or 80

        logger.info(f"HTTP → {host}:{port}")

        # 连接到目标服务器
        remote_reader, remote_writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10
        )

        # 重建请求行（去掉协议前缀，改为相对路径）
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        modified_line = f"{parts[0].decode()} {path} HTTP/1.1\r\n".encode()

        remote_writer.write(modified_line)

        # 转发剩余请求头
        buffer = bytearray()
        while True:
            chunk = await asyncio.wait_for(client_reader.read(BUFFER_SIZE), timeout=5)
            if not chunk:
                break
            buffer.extend(chunk)
            remote_writer.write(chunk)
            if b"\r\n\r\n" in buffer:
                break

        # 双向转发
        await asyncio.gather(
            _relay(remote_reader, client_writer, f"{host}:{port} → client"),
            _relay(client_reader, remote_writer, f"client → {host}:{port}"),
        )

    except asyncio.TimeoutError:
        logger.warning(f"HTTP 连接超时")
    except Exception as e:
        logger.debug(f"HTTP 错误: {e}")
    finally:
        try:
            client_writer.close()
        except Exception:
            pass


async def handle_connect(client_reader, client_writer, host_port: str):
    """处理 HTTPS CONNECT 隧道"""
    remote_reader = None
    remote_writer = None
    try:
        # 解析 host:port
        host, port = host_port.split(":")
        port = int(port)

        logger.info(f"HTTPS → {host}:{port}")

        # 连接到目标服务器
        remote_reader, remote_writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10
        )

        # 告诉客户端隧道已建立
        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()

        # 双向透传（不解密）
        async def relay(src_reader, src_writer, dst_writer, label):
            try:
                while True:
                    chunk = await asyncio.wait_for(
                        src_reader.read(BUFFER_SIZE), timeout=60
                    )
                    if not chunk:
                        break
                    dst_writer.write(chunk)
                    await dst_writer.drain()
            except Exception:
                pass

        await asyncio.gather(
            relay(client_reader, client_writer, remote_writer, "client → remote"),
            relay(remote_reader, remote_writer, client_writer, "remote → client"),
        )

    except asyncio.TimeoutError:
        logger.warning(f"HTTPS CONNECT 超时: {host_port}")
    except Exception as e:
        logger.debug(f"HTTPS 错误: {host_port} - {e}")
    finally:
        try:
            client_writer.close()
        except Exception:
            pass
        if remote_writer:
            try:
                remote_writer.close()
            except Exception:
                pass


async def _relay(reader, writer, label: str):
    """单方向转发"""
    try:
        while True:
            chunk = await asyncio.wait_for(reader.read(BUFFER_SIZE), timeout=60)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except Exception:
        pass


async def handle_client(client_reader, client_writer):
    """处理单个客户端连接"""
    peer = client_writer.get_extra_info("peername")
    try:
        # 读取请求头
        request_data = await asyncio.wait_for(
            client_reader.readuntil(b"\r\n"), timeout=10
        )
        request_line = request_data.strip()

        # 判断请求类型
        if request_line.startswith(b"CONNECT"):
            # HTTPS CONNECT 隧道
            host_port = request_line.split()[1].decode()
            await handle_connect(client_reader, client_writer, host_port)
        else:
            # HTTP 请求
            await handle_http(client_reader, client_writer, request_line)

    except asyncio.TimeoutError:
        logger.debug(f"客户端 {peer} 超时")
    except Exception as e:
        logger.debug(f"客户端 {peer} 错误: {e}")
    finally:
        try:
            client_writer.close()
        except Exception:
            pass


async def main():
    # 检查 Python 版本
    if sys.version_info < (3, 8):
        logger.error("需要 Python 3.8+")
        return

    # 获取本机局域网 IP
    local_ip = socket.gethostbyname(socket.gethostname())

    server = await asyncio.start_server(handle_client, HOST, PORT)

    print("=" * 55)
    print("  PC 端 HTTP 代理服务器已启动")
    print("=" * 55)
    print(f"  监听地址:  {HOST}:{PORT}")
    print(f"  本机 IP:   {local_ip}")
    print(f"  代理 URL:  http://{local_ip}:{PORT}")
    print()
    print("  NAS 配置（docker-compose.yml 中 backend 的 environment）：")
    print(f"    - SCRAPER_PROXY_URL=http://{local_ip}:{PORT}")
    print()
    print("  ⚠️  确保电脑 VPN 已开启，且 NAS 能 ping 通本机 IP")
    print("  按 Ctrl+C 停止")
    print("=" * 55)

    logger.info(f"代理服务器启动在 {HOST}:{PORT}")

    try:
        async with server:
            await server.serve_forever()
    except KeyboardInterrupt:
        print("\n代理服务器已停止")
        logger.info("代理服务器已停止")


if __name__ == "__main__":
    asyncio.run(main())