from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QCompleter
from PySide6.QtCore import Qt, QDate
from qfluentwidgets import (MessageBoxBase, SubtitleLabel, LineEdit, 
                            CalendarPicker, ComboBox, PrimaryPushButton, PushButton)

class AddPatientDialog(MessageBoxBase):
    """ 新建患者对话框 """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("新建患者档案", self)
        
        # 表单控件
        self.id_edit = LineEdit(self)
        self.id_edit.setPlaceholderText("病历号/身份证号 (必填)")
        self.id_edit.setClearButtonEnabled(True)

        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("姓名 (必填)")
        self.name_edit.setClearButtonEnabled(True)

        self.gender_combo = ComboBox(self)
        self.gender_combo.addItems(["男 (Male)", "女 (Female)"])
        self.gender_combo.setPlaceholderText("性别")

        self.birth_picker = CalendarPicker(self)
        self.birth_picker.setDate(QDate.currentDate().addYears(-30)) # 默认30岁
        self.birth_picker.setDateFormat(Qt.ISODate) # yyyy-MM-dd

        self.phone_edit = LineEdit(self)
        self.phone_edit.setPlaceholderText("联系电话 (选填)")

        # 布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.id_edit)
        self.viewLayout.addWidget(self.name_edit)
        self.viewLayout.addWidget(self.gender_combo)
        self.viewLayout.addWidget(self.birth_picker)
        self.viewLayout.addWidget(self.phone_edit)

        # 设置确定/取消按钮文本
        self.yesButton.setText("创建")
        self.cancelButton.setText("取消")

        # 验证
        self.yesButton.setDisabled(True)
        self.id_edit.textChanged.connect(self.validate_input)
        self.name_edit.textChanged.connect(self.validate_input)

        # 设置最小宽度
        self.widget.setMinimumWidth(350)

    def validate_input(self):
        """ 简单校验：ID和姓名不能为空 """
        is_valid = bool(self.id_edit.text().strip() and self.name_edit.text().strip())
        self.yesButton.setEnabled(is_valid)

    def get_data(self):
        """ 获取表单数据 """
        return {
            "patient_id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "gender": "M" if self.gender_combo.currentIndex() == 0 else "F",
            "birth_date": self.birth_picker.date.toPython(), # 转换为 Python date 对象
            "phone": self.phone_edit.text().strip()
        }

