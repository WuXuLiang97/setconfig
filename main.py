import configparser
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QByteArray, QEvent, QPoint, QSize, Qt, QTime, QTimer, QUrl, pyqtSlot, QSettings
from PyQt5.QtGui import QDesktopServices, QKeySequence, QMouseEvent, QTextCursor, QPixmap
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                             QKeySequenceEdit, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                             QTimeEdit, QVBoxLayout, QWidget, QTabWidget, QSizePolicy, QGridLayout, QScrollArea,
                             QInputDialog, QGroupBox, QListWidget, QListWidgetItem)
import sys
import shutil
import os

def list_subfolders(path):
    """返回指定路径下所有子文件夹的完整路径"""
    subfolders = [f.path for f in os.scandir(path) if f.is_dir()]
    return subfolders

class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("配置替换工具")
        self.resize(660, 370)

        self.settings = QSettings("config.ini", QSettings.IniFormat)
        self._loading = False

        # 用于暂存从配置中读取的待恢复场景名称
        self._pending_scene = None
        self._pending_restore = None
        self._pending_mgr = None

        # 存储 owner -> 配置文件夹路径 的映射
        self.data = {}

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ========== 1. 源路径设置区域 ==========
        src_group = QGroupBox("userdata 目标路径")
        src_layout = QHBoxLayout(src_group)
        self.src_label = QLabel("路径：")
        self.src_line_edit = QLineEdit()
        self.src_line_edit.setPlaceholderText("选择或输入 userdata 文件夹路径...")
        self.src_browse_btn = QPushButton("浏览...")
        self.src_browse_btn.clicked.connect(self.select_src_path)
        src_layout.addWidget(self.src_label)
        src_layout.addWidget(self.src_line_edit, 1)
        src_layout.addWidget(self.src_browse_btn)
        main_layout.addWidget(src_group)

        # ========== 2. 使用 QTabWidget 分离主要功能 ==========
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- 2.1 导出/还原标签页 ---
        operate_tab = QWidget()
        operate_layout = QVBoxLayout(operate_tab)

        # 导出区域
        export_group = QGroupBox("导出配置到场景")
        export_layout = QGridLayout(export_group)
        export_layout.addWidget(QLabel("备注（角色名称）："), 0, 0)
        self.role_name_edit = QLineEdit()
        self.role_name_edit.setPlaceholderText("必填，不能重复")
        export_layout.addWidget(self.role_name_edit, 0, 1, 1, 2)
        export_layout.addWidget(QLabel("场景名称："), 1, 0)
        self.scene_combo = QComboBox()
        self.scene_combo.setMinimumWidth(200)
        self.scene_combo.setEditable(False)
        export_layout.addWidget(self.scene_combo, 1, 1)
        export_layout.addWidget(QLabel("配置路径："), 2, 0)

        # 配置路径选择组合框（用于显示 owner / 文件夹名）
        self.config_path_cbx = QComboBox()
        self.config_path_cbx.setMinimumWidth(200)
        self.config_path_cbx.setEditable(False)
        self.config_path_cbx.currentTextChanged.connect(self.on_config_path_selected)

        # 显示实际路径的只读编辑框（方便查看）
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setReadOnly(True)
        self.config_path_edit.setPlaceholderText("选中的配置文件夹实际路径")

        self.config_browse_btn = QPushButton("刷新列表")
        self.config_browse_btn.clicked.connect(self.refresh_config_list)   # 改为刷新列表

        export_layout.addWidget(self.config_path_cbx, 2, 1)
        export_layout.addWidget(self.config_browse_btn, 2, 2)
        export_layout.addWidget(self.config_path_edit, 3, 0, 1, 3)   # 将路径显示放在按钮下方
        self.export_btn = QPushButton("导出配置")
        self.export_btn.clicked.connect(self.export_config)
        export_layout.addWidget(self.export_btn, 4, 0, 1, 3)
        export_layout.setColumnStretch(1, 1)
        operate_layout.addWidget(export_group)

        # 还原区域
        restore_group = QGroupBox("从场景还原到 userdata")
        restore_layout = QGridLayout(restore_group)
        restore_layout.addWidget(QLabel("选择场景："), 0, 0)
        self.restore_scene_combo = QComboBox()
        self.restore_scene_combo.setMinimumWidth(200)
        self.restore_scene_combo.setEditable(False)
        self.refresh_scene_btn = QPushButton("刷新场景列表")
        self.refresh_scene_btn.clicked.connect(self.refresh_all_scene_combos)
        restore_layout.addWidget(self.restore_scene_combo, 0, 1)
        restore_layout.addWidget(self.refresh_scene_btn, 0, 2)
        self.restore_btn = QPushButton("覆盖到 userdata")
        self.restore_btn.clicked.connect(self.restore_to_userdata)
        restore_layout.addWidget(self.restore_btn, 1, 0, 1, 3)
        operate_layout.addWidget(restore_group)

        operate_layout.addStretch()
        self.tab_widget.addTab(operate_tab, "导出 / 还原")

        # --- 2.2 配置管理标签页 ---
        manage_tab = QWidget()
        manage_layout = QVBoxLayout(manage_tab)

        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("选择场景："))
        self.scene_mgr_combo = QComboBox()
        self.scene_mgr_combo.setEditable(False)
        self.scene_mgr_combo.currentTextChanged.connect(self.on_scene_mgr_changed)
        sel_layout.addWidget(self.scene_mgr_combo, 1)
        self.refresh_scene_mgr_btn = QPushButton("刷新场景列表")
        self.refresh_scene_mgr_btn.clicked.connect(self.refresh_all_scene_combos)
        sel_layout.addWidget(self.refresh_scene_mgr_btn)

        self.add_scene_btn = QPushButton("新增场景")
        self.add_scene_btn.clicked.connect(self.on_add_scene)
        sel_layout.addWidget(self.add_scene_btn)
        self.del_scene_btn = QPushButton("删除场景")
        self.del_scene_btn.clicked.connect(self.on_delete_scene)
        sel_layout.addWidget(self.del_scene_btn)

        manage_layout.addLayout(sel_layout)

        list_btn_layout = QHBoxLayout()
        self.role_list = QListWidget()
        self.role_list.setSelectionMode(QListWidget.SingleSelection)
        list_btn_layout.addWidget(self.role_list, 3)
        btn_vbox = QVBoxLayout()
        self.modify_btn = QPushButton("修改文件夹名称")
        self.modify_btn.clicked.connect(self.on_modify_folder)
        self.delete_btn = QPushButton("删除文件夹")
        self.delete_btn.clicked.connect(self.on_delete_folder)
        btn_vbox.addWidget(self.modify_btn)
        btn_vbox.addWidget(self.delete_btn)
        btn_vbox.addStretch()
        list_btn_layout.addLayout(btn_vbox, 1)
        manage_layout.addLayout(list_btn_layout)

        manage_layout.addStretch()
        self.tab_widget.addTab(manage_tab, "配置管理")

        # 连接实时保存的信号
        self.setup_connections()

        # 加载保存的设置（界面状态、窗口几何、上次选中的场景名称）
        self.load_settings()
        # 刷新所有下拉框（基于实际文件夹），并恢复上次选中的场景
        self.refresh_all_scene_combos()
        # 如果 userdata 路径已有保存值，则刷新配置列表
        if self.src_line_edit.text():
            self.refresh_config_list()

    def get_scene_root(self):
        """返回场景存储的根目录（程序运行目录下的 data 文件夹），如果不存在则创建"""
        root = os.path.join(os.getcwd(), "data")
        os.makedirs(root, exist_ok=True)
        return root

    def setup_connections(self):
        """为需要实时保存的控件连接信号"""
        self.src_line_edit.textChanged.connect(self.on_setting_changed)
        self.role_name_edit.textChanged.connect(self.on_setting_changed)
        # 下拉框切换选项时保存当前选择
        self.scene_combo.currentTextChanged.connect(self.on_setting_changed)
        self.config_path_cbx.currentTextChanged.connect(self.on_setting_changed)
        self.restore_scene_combo.currentTextChanged.connect(self.on_setting_changed)
        self.scene_mgr_combo.currentTextChanged.connect(self.on_setting_changed)

    def on_setting_changed(self):
        if not self._loading:
            self.save_settings()

    def refresh_all_scene_combos(self):
        """扫描 data 目录下的文件夹，更新所有场景下拉框，并恢复上次选中的场景"""
        if self._loading:
            return
        self._loading = True

        scene_root = self.get_scene_root()
        dirs = []
        try:
            for item in os.listdir(scene_root):
                if os.path.isdir(os.path.join(scene_root, item)):
                    dirs.append(item)
        except Exception as e:
            print(f"扫描目录失败：{e}")

        self._update_combo_with_dirs(self.scene_combo, dirs)
        self._update_combo_with_dirs(self.restore_scene_combo, dirs)
        self._update_combo_with_dirs(self.scene_mgr_combo, dirs)

        if self._pending_scene and self._pending_scene in dirs:
            self.scene_combo.setCurrentText(self._pending_scene)
        if self._pending_restore and self._pending_restore in dirs:
            self.restore_scene_combo.setCurrentText(self._pending_restore)
        if self._pending_mgr and self._pending_mgr in dirs:
            self.scene_mgr_combo.setCurrentText(self._pending_mgr)

        self._pending_scene = None
        self._pending_restore = None
        self._pending_mgr = None

        self._loading = False
        self.save_settings()

    def _update_combo_with_dirs(self, combo, dirs):
        """辅助方法：下拉框只显示实际存在的文件夹列表"""
        current_text = combo.currentText()
        combo.clear()
        if dirs:
            combo.addItems(sorted(dirs))
        if current_text and current_text in dirs:
            combo.setCurrentText(current_text)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)
        else:
            combo.setCurrentIndex(-1)

    # ================= 新增/修改的方法 =================
    def refresh_config_list(self):
        src_path = self.src_line_edit.text().strip()
        if not src_path:
            self.config_path_cbx.clear()
            self.config_path_edit.clear()
            QMessageBox.warning(self, "提示", "请先填写或选择 userdata 目标路径")
            return

        if not os.path.isdir(src_path):
            self.config_path_cbx.clear()
            self.config_path_edit.clear()
            QMessageBox.warning(self, "路径错误", f"userdata 路径不存在：\n{src_path}")
            return

        # 获取所有子文件夹，并按修改时间降序排序（最新的在前）
        subfolders = list_subfolders(src_path)
        subfolders.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        new_data = {}
        for sub in subfolders:
            folder_name = os.path.basename(sub)
            ini_path = os.path.join(sub, "friend.ini")
            owner = None
            try:
                with open(ini_path, 'r', encoding='gbk') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line[0] in (';', '#'):
                            continue
                        if '=' in line:
                            k, v = line.split('=', 1)
                            if k.strip() == 'owner':
                                owner = v.strip()
                                break
            except Exception as e:
                print(f"读取 {ini_path} 失败: {e}")

            if owner:
                key = owner
            else:
                continue  # 没有 owner 则跳过（与原逻辑一致）
            if key in new_data:
                new_data[f"{key}_{folder_name}"] = sub
            else:
                new_data[key] = sub

        self.data = new_data

        # 更新组合框（按插入顺序，即修改时间顺序）
        self._loading = True
        current_key = self.config_path_cbx.currentText()
        self.config_path_cbx.clear()
        if self.data:
            # 直接使用字典的 keys 顺序（已按修改时间排序）
            self.config_path_cbx.addItems(self.data.keys())
            if current_key and current_key in self.data:
                self.config_path_cbx.setCurrentText(current_key)
            else:
                self.config_path_cbx.setCurrentIndex(0)
        else:
            self.config_path_edit.clear()
            QMessageBox.information(self, "扫描结果", "未在 userdata 目录下找到任何有效子文件夹")
        self._loading = False
        self.on_setting_changed()

    def on_config_path_selected(self, key):
        """当下拉框选中某个键时，显示真实路径并自动填充角色名称"""
        if not key or key not in self.data:
            self.config_path_edit.clear()
            return
        real_path = self.data[key]
        self.config_path_edit.setText(real_path)
        # 自动填充角色名称（方便导出，用户可手动修改）
        if not self._loading:
            self.role_name_edit.setText(key)

    # ================= 原有方法的修改 =================
    def select_src_path(self):
        last_dir = self.settings.value("last_src_browse_path", "")
        if last_dir and not os.path.exists(last_dir):
            last_dir = ""
        path = QFileDialog.getExistingDirectory(self, "选择userdata文件夹", last_dir)
        if path:
            self.src_line_edit.setText(path)
            self.settings.setValue("last_src_browse_path", path)
            # 立即刷新配置列表
            self.refresh_config_list()

    def export_config(self):
        role_name = self.role_name_edit.text().strip()
        scene = self.scene_combo.currentText().strip()
        # 获取当前选中的配置标识（owner 或文件夹名）
        selected_key = self.config_path_cbx.currentText().strip()

        if not role_name:
            QMessageBox.warning(self, "警告", "请填写角色名称！")
            return
        if not scene:
            QMessageBox.warning(self, "警告", "请选择场景名称！")
            return
        if not selected_key or selected_key not in self.data:
            QMessageBox.warning(self, "警告", "请先刷新配置列表并选择一个有效的配置项！")
            return

        config_path = self.data[selected_key]
        if not os.path.exists(config_path):
            QMessageBox.warning(self, "警告", f"配置路径不存在：\n{config_path}\n请重新刷新列表")
            return

        scene_root = self.get_scene_root()
        target_dir = os.path.join(scene_root, scene, role_name)
        folder_name = os.path.basename(config_path)
        dest_path = os.path.join(target_dir, folder_name)

        try:
            if os.path.exists(dest_path):
                reply = QMessageBox.question(self, "确认覆盖",
                                             f"目标路径已存在：\n{dest_path}\n是否覆盖？",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
                shutil.rmtree(dest_path)
            shutil.copytree(config_path, dest_path)
            QMessageBox.information(self, "导出成功", f"配置已导出到：\n{dest_path}")
            self.refresh_all_scene_combos()
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"错误信息：{str(e)}")

    def restore_to_userdata(self):
        # ... 原有代码保持不变 ...
        src_root = self.src_line_edit.text().strip()
        scene = self.restore_scene_combo.currentText().strip()

        if not src_root:
            QMessageBox.warning(self, "警告", "请先选择 userdata 路径！")
            return
        if not scene:
            QMessageBox.warning(self, "警告", "请选择要还原的场景名称！")
            return

        scene_root = self.get_scene_root()
        scene_dir = os.path.join(scene_root, scene)
        if not os.path.isdir(scene_dir):
            QMessageBox.warning(self, "警告", f"场景文件夹不存在：\n{scene_dir}")
            return

        role_dirs = []
        try:
            for item in os.listdir(scene_dir):
                item_path = os.path.join(scene_dir, item)
                if os.path.isdir(item_path):
                    role_dirs.append(item)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取场景目录失败：{str(e)}")
            return

        if not role_dirs:
            QMessageBox.warning(self, "警告", f"场景目录下没有找到任何角色子目录：\n{scene_dir}")
            return

        reply = QMessageBox.question(self, "确认覆盖",
                                     f"即将扫描场景 [{scene}] 下的 {len(role_dirs)} 个角色目录，\n"
                                     f"并将每个角色目录内的配置文件夹覆盖到：\n{src_root}\n\n是否继续？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        success_count = 0
        skip_count = 0
        skipped_details = []

        for role in role_dirs:
            role_path = os.path.join(scene_dir, role)
            sub_folders = []
            try:
                for f in os.listdir(role_path):
                    f_path = os.path.join(role_path, f)
                    if os.path.isdir(f_path):
                        sub_folders.append(f)
            except Exception as e:
                skip_count += 1
                skipped_details.append(f"{role} (无法读取目录: {str(e)})")
                continue

            if len(sub_folders) == 0:
                skip_count += 1
                skipped_details.append(f"{role} (没有子文件夹)")
                continue
            elif len(sub_folders) > 1:
                selected, ok = QInputDialog.getItem(self, f"选择配置文件夹 - {role}",
                                                    f"角色 [{role}] 目录下有多个配置文件夹，请选择要还原的：",
                                                    sub_folders, 0, False)
                if not ok or not selected:
                    skip_count += 1
                    skipped_details.append(f"{role} (用户取消选择)")
                    continue
                target_folder = selected
            else:
                target_folder = sub_folders[0]

            src_config = os.path.join(role_path, target_folder)
            dst_config = os.path.join(src_root, target_folder)

            try:
                if os.path.exists(dst_config):
                    shutil.rmtree(dst_config)
                shutil.copytree(src_config, dst_config)
                success_count += 1
            except Exception as e:
                skip_count += 1
                skipped_details.append(f"{role}/{target_folder} (复制失败: {str(e)})")

        msg = f"覆盖完成！\n成功：{success_count} 个\n跳过：{skip_count} 个"
        if skipped_details:
            msg += "\n\n跳过的详情：\n" + "\n".join(skipped_details[:10])
            if len(skipped_details) > 10:
                msg += f"\n... 共 {len(skipped_details)} 条"
        QMessageBox.information(self, "执行结果", msg)

    # ---------- 场景管理相关方法 ----------
    def on_add_scene(self):
        # ... 与原来相同，无需修改 ...
        new_name, ok = QInputDialog.getText(self, "新增场景", "请输入场景名称：")
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if not self.is_valid_filename(new_name):
            QMessageBox.warning(self, "警告", "场景名称不能包含 / \\ : * ? \" < > | 等字符")
            return
        scene_root = self.get_scene_root()
        new_path = os.path.join(scene_root, new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "警告", f"场景 [{new_name}] 已存在！")
            return
        try:
            os.mkdir(new_path)
            QMessageBox.information(self, "成功", f"场景 [{new_name}] 创建成功")
            self.refresh_all_scene_combos()
            self.scene_mgr_combo.setCurrentText(new_name)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建场景失败：{str(e)}")

    def on_delete_scene(self):
        # ... 与原来相同 ...
        scene = self.scene_mgr_combo.currentText().strip()
        if not scene:
            QMessageBox.warning(self, "警告", "请先选择一个场景！")
            return
        scene_root = self.get_scene_root()
        scene_path = os.path.join(scene_root, scene)
        if not os.path.isdir(scene_path):
            QMessageBox.warning(self, "错误", f"场景文件夹不存在：{scene_path}")
            self.refresh_all_scene_combos()
            return
        reply = QMessageBox.question(self, "确认删除场景",
                                     f"确定要删除场景 [ {scene} ] 及其所有内容吗？\n路径：{scene_path}\n此操作不可恢复！",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            shutil.rmtree(scene_path)
            QMessageBox.information(self, "成功", f"场景 [ {scene} ] 已删除")
            self.refresh_all_scene_combos()
            self.role_list.clear()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除场景失败：{str(e)}")

    def on_scene_mgr_changed(self, scene_name):
        # ... 与原来相同 ...
        if not scene_name:
            self.role_list.clear()
            return
        scene_root = self.get_scene_root()
        scene_dir = os.path.join(scene_root, scene_name)
        if not os.path.isdir(scene_dir):
            self.role_list.clear()
            return
        roles = []
        try:
            for item in os.listdir(scene_dir):
                if os.path.isdir(os.path.join(scene_dir, item)):
                    roles.append(item)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"读取场景目录失败：{str(e)}")
            self.role_list.clear()
            return
        self.role_list.clear()
        self.role_list.addItems(sorted(roles))

    def on_modify_folder(self):
        # ... 与原来相同 ...
        current_item = self.role_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个文件夹！")
            return
        old_name = current_item.text()
        scene = self.scene_mgr_combo.currentText()
        if not scene:
            QMessageBox.warning(self, "警告", "请先选择一个场景！")
            return
        scene_root = self.get_scene_root()
        old_path = os.path.join(scene_root, scene, old_name)
        if not os.path.isdir(old_path):
            QMessageBox.warning(self, "错误", f"文件夹不存在：{old_path}")
            self.refresh_all_scene_combos()
            return

        new_name, ok = QInputDialog.getText(self, "修改文件夹名称", "请输入新名称：", text=old_name)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name == old_name:
            return
        if not self.is_valid_filename(new_name):
            QMessageBox.warning(self, "警告", "文件夹名称不能包含 / \\ : * ? \" < > | 等字符")
            return
        new_path = os.path.join(scene_root, scene, new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "警告", f"目标文件夹已存在：{new_name}")
            return

        try:
            os.rename(old_path, new_path)
            QMessageBox.information(self, "成功", f"已重命名为：{new_name}")
            self.on_scene_mgr_changed(scene)
            self.refresh_all_scene_combos()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重命名失败：{str(e)}")

    def on_delete_folder(self):
        # ... 与原来相同 ...
        current_item = self.role_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择一个文件夹！")
            return
        role_name = current_item.text()
        scene = self.scene_mgr_combo.currentText()
        if not scene:
            QMessageBox.warning(self, "警告", "请先选择一个场景！")
            return
        scene_root = self.get_scene_root()
        target_path = os.path.join(scene_root, scene, role_name)
        if not os.path.isdir(target_path):
            QMessageBox.warning(self, "错误", f"文件夹不存在：{target_path}")
            self.refresh_all_scene_combos()
            return

        reply = QMessageBox.question(self, "确认删除",
                                     f"确定要删除文件夹 [{role_name}] 及其所有内容吗？\n路径：{target_path}\n此操作不可恢复！",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            shutil.rmtree(target_path)
            QMessageBox.information(self, "成功", f"已删除文件夹：{role_name}")
            self.on_scene_mgr_changed(scene)
            self.refresh_all_scene_combos()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败：{str(e)}")

    @staticmethod
    def is_valid_filename(name):
        invalid_chars = r'\/:*?"<>|'
        return not any(c in invalid_chars for c in name)

    # ================= 设置保存/加载（修改部分） =================
    def load_settings(self):
        """加载所有控件状态、窗口几何以及上次选中的场景名称"""
        self._loading = True

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(660, 370)
            self.move(QApplication.primaryScreen().availableGeometry().center() - self.rect().center())

        self.src_line_edit.setText(self.settings.value("src_path", ""))
        self.role_name_edit.setText(self.settings.value("role_name", ""))
        # 不再加载 config_path_edit，改为加载 config_path_cbx 选中的键
        self._pending_scene = self.settings.value("scene_name", "")
        self._pending_restore = self.settings.value("restore_scene", "")
        self._pending_mgr = self.settings.value("scene_mgr_current", "")
        # 保存上次选中的配置标识（owner/文件夹名）
        self._pending_config_key = self.settings.value("config_selected_key", "")

        self._loading = False

    def save_settings(self):
        """保存所有控件状态、窗口几何以及当前选中的场景"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("src_path", self.src_line_edit.text())
        self.settings.setValue("role_name", self.role_name_edit.text())
        self.settings.setValue("scene_name", self.scene_combo.currentText())
        self.settings.setValue("restore_scene", self.restore_scene_combo.currentText())
        self.settings.setValue("scene_mgr_current", self.scene_mgr_combo.currentText())
        # 保存当前选中的配置下拉框文本
        self.settings.setValue("config_selected_key", self.config_path_cbx.currentText())
        self.settings.sync()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())