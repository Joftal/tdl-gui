import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_requirements():
    """检查并安装必要的依赖"""
    print("正在检查依赖...")
    try:
        import PyInstaller
    except ImportError:
        print("正在安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])

def clean_build_dirs():
    """清理构建目录"""
    print("正在清理构建目录...")
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"删除 {dir_name} 目录")
            shutil.rmtree(dir_name)

def build_executable():
    """执行打包操作"""
    print("开始打包...")
    
    # 检查必要文件
    required_files = ['tdl_flet.py', 'tdl_flet.spec', 'tdl.exe', 'ico.ico', 'file_version_info.txt']
    for file in required_files:
        if not os.path.exists(file):
            print(f"错误: 找不到必要的文件 {file}")
            return False
    
    try:
        # 使用 PyInstaller 打包
        # 当使用 spec 文件时，只需要最基本的参数
        subprocess.check_call([
            sys.executable, 
            "-m", 
            "PyInstaller",
            "--clean",  # 清理临时文件
            "--noconfirm",  # 不询问确认
            "tdl_flet.spec"  # 使用 spec 文件
        ])
        
        # 检查是否成功创建了可执行文件
        exe_path = os.path.join('dist', 'TDL下载器.exe')
        if os.path.exists(exe_path):
            print(f"\n打包成功！可执行文件位置: {exe_path}")
            # 获取文件大小
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"文件大小: {size_mb:.2f} MB")
            
            # 复制 tdl.exe 到 dist 目录
            print("\n正在复制 tdl.exe 到输出目录...")
            shutil.copy2('tdl.exe', os.path.join('dist', 'tdl.exe'))
            print("复制完成！")
            
            return True
        else:
            print("错误: 未找到生成的可执行文件")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"打包过程中出错: {str(e)}")
        return False
    except Exception as e:
        print(f"发生未知错误: {str(e)}")
        return False

def main():
    print("=== TDL下载器打包工具 ===")
    
    # 检查依赖
    check_requirements()
    
    # 清理旧的构建文件
    clean_build_dirs()
    
    # 执行打包
    if build_executable():
        print("\n打包完成！")
        print("\n提示：")
        print("1. 可执行文件在 dist 目录中")
        print("2. 确保 tdl.exe 与程序在同一目录")
        print("3. 如需分发，请将 dist 目录中的所有文件一起分发")
    else:
        print("\n打包失败！")

if __name__ == "__main__":
    main() 