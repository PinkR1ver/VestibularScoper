from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
import os

# 定义数据库文件路径
DB_PATH = "vestibular_data.db"

# 创建基类
Base = declarative_base()

class DatabaseManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._init_db()
        return cls._instance
    
    def _init_db(self):
        # 使用 SQLite
        self.engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
        
        # 创建会话工厂
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        # === 关键修正：必须在创建表之前导入所有模型 ===
        # 这样 Base.metadata 才能收集到这些表的定义
        from app.database.models import Patient, ExamRecord
        
        # 创建表 (如果不存在)
        Base.metadata.create_all(self.engine)

    def get_session(self):
        return self.Session()
        
    def close(self):
        self.Session.remove()

# 全局单例访问点
db = DatabaseManager()

