from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.db_manager import Base

class Patient(Base):
    """ 患者信息表 """
    __tablename__ = 'patients'

    id = Column(Integer, primary_key=True)
    patient_id = Column(String(50), unique=True, nullable=False, comment="医院病历号/身份证号")
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=True) # 'M', 'F'
    birth_date = Column(DateTime, nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联检查记录 (一对多)
    records = relationship("ExamRecord", back_populates="patient", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Patient(name={self.name}, id={self.patient_id})>"

class ExamRecord(Base):
    """ 检查记录表 (每次检查生成一条) """
    __tablename__ = 'exam_records'

    id = Column(Integer, primary_key=True)
    patient_pk = Column(Integer, ForeignKey('patients.id'), nullable=False)
    
    exam_date = Column(DateTime, default=datetime.now)
    video_path = Column(String(255), nullable=True, comment="原始视频文件路径")
    diagnosis_notes = Column(Text, nullable=True, comment="医生诊断备注")
    
    # 预留字段：存储眼震分析结果 (JSON格式或指向单独的分析表)
    # analysis_data_path = Column(String(255)) 

    # 关联患者
    patient = relationship("Patient", back_populates="records")

    def __repr__(self):
        return f"<ExamRecord(date={self.exam_date}, patient={self.patient_pk})>"

