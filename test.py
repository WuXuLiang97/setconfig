import os
data = {}
def list_subfolders(path):
    """返回指定路径下所有子文件夹的完整路径"""
    subfolders = [f.path for f in os.scandir(path) if f.is_dir()]
    return subfolders

# 使用示例
folder_path = r"D:\asktao\userdata"   # Windows示例，Linux/macOS改为 "/path/to/folder"
subfolders = list_subfolders(folder_path)
for sf in subfolders:
    print(sf)
    # ---------- 新增：读取 friend.ini 中的 owner 键 ----------
    ini_path = os.path.join(sf, "friend.ini")
    try:
        with open(ini_path, 'r', encoding='gbk') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释行（可选）
                if not line or line[0] in (';', '#'):
                    continue
                # 包含等号才可能是键值对
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() == 'owner':
                        owner_value = value.strip()
                        data[owner_value] = sf
                        print(owner_value)
    except Exception as e:
        print(f"读取 owner 失败: {e}")
print(data)