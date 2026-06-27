#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建所有必要的数据库表
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.database import Base, engine
from backend.app.models.lead import Lead, LeadSource, LeadNote, Tag
from backend.app.models.user import User

def init_db():
    """初始化数据库，创建所有表"""
    print("正在连接数据库...")
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库表创建成功！")
        
        # 列出已创建的表
        tables = Base.metadata.tables.keys()
        print(f"已创建的表: {', '.join(tables)}")
        
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)
