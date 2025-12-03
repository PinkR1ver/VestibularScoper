from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem
from PySide6.QtCore import Qt, Signal
from qfluentwidgets import (SubtitleLabel, PrimaryPushButton, TableWidget, 
                            FluentIcon, LineEdit, InfoBar, InfoBarPosition, MessageBox, TransparentToolButton)

from app.database.db_manager import db
from app.database.models import Patient
from app.ui.components.add_patient_dialog import AddPatientDialog

class PatientManagerInterface(QWidget):
    """ 患者管理界面 """
    
    patient_selected = Signal(int, str) # 信号：选中患者 (id, name)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("PatientManagerInterface")
        
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(30, 30, 30, 30)
        self.v_layout.setSpacing(20)

        # --- 顶部工具栏 ---
        self.h_layout = QHBoxLayout()
        
        self.title_label = SubtitleLabel("患者列表 (Patients)", self)
        
        self.search_bar = LineEdit(self)
        self.search_bar.setPlaceholderText("搜索姓名或病历号...")
        self.search_bar.setFixedWidth(300)
        self.search_bar.textChanged.connect(self.load_patients) # 实时搜索

        self.btn_add = PrimaryPushButton(FluentIcon.ADD, "新建患者", self)
        self.btn_add.clicked.connect(self.show_add_patient_dialog)

        self.h_layout.addWidget(self.title_label)
        self.h_layout.addStretch(1)
        self.h_layout.addWidget(self.search_bar)
        self.h_layout.addWidget(self.btn_add)

        # --- 表格区域 ---
        self.table = TableWidget(self)
        self.table.setColumnCount(6) # ID, 病历号, 姓名, 性别, 出生日期, 操作
        self.table.setHorizontalHeaderLabels(['ID', '病历号', '姓名', '性别', '出生日期', '操作'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(TableWidget.NoEditTriggers) # 禁止直接编辑
        
        # 选中行时触发
        self.table.itemDoubleClicked.connect(self.on_row_double_clicked)

        self.v_layout.addLayout(self.h_layout)
        self.v_layout.addWidget(self.table)

        # 初始化数据
        self.load_patients()

    def load_patients(self):
        """ 从数据库加载患者列表 """
        search_text = self.search_bar.text().strip()
        session = db.get_session()
        
        query = session.query(Patient)
        if search_text:
            # 模糊搜索
            query = query.filter(
                (Patient.name.contains(search_text)) | 
                (Patient.patient_id.contains(search_text))
            )
        
        patients = query.order_by(Patient.created_at.desc()).all()
        
        self.table.setRowCount(len(patients))
        
        for row, p in enumerate(patients):
            self.table.setItem(row, 0, QTableWidgetItem(str(p.id)))
            self.table.setItem(row, 1, QTableWidgetItem(p.patient_id))
            self.table.setItem(row, 2, QTableWidgetItem(p.name))
            self.table.setItem(row, 3, QTableWidgetItem(p.gender or "-"))
            
            birth_str = p.birth_date.strftime("%Y-%m-%d") if p.birth_date else "-"
            self.table.setItem(row, 4, QTableWidgetItem(birth_str))
            
            # 添加删除按钮
            self._add_action_buttons(row, p.id, p.name)
            
            # 存储 Patient 对象在第一列的 item 数据里，方便后续获取
            self.table.item(row, 0).setData(Qt.UserRole, p)

        session.close()

    def _add_action_buttons(self, row, patient_id, patient_name):
        """ 在表格行添加操作按钮 """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 删除按钮
        btn_delete = TransparentToolButton(FluentIcon.DELETE, self)
        btn_delete.setToolTip("删除患者")
        btn_delete.clicked.connect(lambda: self.delete_patient(patient_id, patient_name))
        
        layout.addStretch(1)
        layout.addWidget(btn_delete)
        layout.addStretch(1)
        
        self.table.setCellWidget(row, 5, widget)

    def delete_patient(self, patient_id, patient_name):
        """ 删除患者 """
        w = MessageBox(
            '确认删除', 
            f'确定要删除患者 "{patient_name}" 及其所有检查记录吗？此操作不可恢复。', 
            self
        )
        if w.exec():
            session = db.get_session()
            try:
                patient = session.query(Patient).get(patient_id)
                if patient:
                    session.delete(patient)
                    session.commit()
                    
                    InfoBar.success(
                        title='已删除',
                        content=f"患者 {patient_name} 删除成功",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.load_patients()
            except Exception as e:
                InfoBar.error(
                    title='错误',
                    content=f"删除失败: {str(e)}",
                    parent=self
                )
            finally:
                session.close()

    def on_row_double_clicked(self, item):
        """ 双击行进入检查 """
        row = item.row()
        patient_item = self.table.item(row, 0)
        if not patient_item:
            return
            
        patient = patient_item.data(Qt.UserRole)
        
        # 发送信号通知主窗口
        self.patient_selected.emit(patient.id, patient.name)

    def show_add_patient_dialog(self):
        """ 显示添加患者对话框 """
        w = AddPatientDialog(self)
        if w.exec():
            data = w.get_data()
            
            session = db.get_session()
            try:
                # 检查 ID 是否重复
                existing = session.query(Patient).filter_by(patient_id=data['patient_id']).first()
                if existing:
                    InfoBar.error(
                        title='错误',
                        content=f"病历号 {data['patient_id']} 已存在",
                        parent=self
                    )
                    return

                new_p = Patient(
                    patient_id=data['patient_id'],
                    name=data['name'],
                    gender=data['gender'],
                    birth_date=data['birth_date'],
                    phone=data['phone']
                )
                session.add(new_p)
                session.commit()
                
                InfoBar.success(
                    title='成功',
                    content=f"已添加患者: {new_p.name}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
                self.load_patients()
            except Exception as e:
                InfoBar.error(
                    title='错误',
                    content=str(e),
                    parent=self
                )
            finally:
                session.close()
