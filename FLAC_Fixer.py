import os
import sys
import subprocess
from pathlib import Path

# 尝试导入 mutagen，若未安装请先：pip install mutagen
try:
    from mutagen.flac import FLAC, Picture
except ImportError:
    print("错误: 缺少必要库 'mutagen'。请运行: pip install mutagen")
    sys.exit(1)

# --- 打包路径自适应逻辑 ---
if getattr(sys, 'frozen', False):
    # 如果是 PyInstaller 打包后的运行环境
    BASE_PATH = Path(sys._MEIPASS)
else:
    # 如果是普通的 .py 脚本运行环境
    BASE_PATH = Path(__file__).parent

# 工具路径指向
LIBS_DIR = BASE_PATH / "libs"
FLAC_EXE = str(LIBS_DIR / "flac.exe")
PINGO_EXE = str(LIBS_DIR / "pingo.exe")

def process_flac_fix_mutagen(file_path):
    f_path = Path(file_path)
    print(f"\n{'='*50}")
    print(f"正在优化: {f_path.name}")

    # 切换工作目录到音频文件所在位置，便于处理临时文件
    os.chdir(f_path.parent)
    
    # 临时文件定义
    temp_img = "temp_pingo_cover.jpg"
    orig_bak = f_path.with_name(f"{f_path.stem}_orig.flac")

    try:
        # --- 步骤 1: 使用 Mutagen 提取并优化图片 (避开控制台编码错误) ---
        audio = FLAC(f_path)
        if audio.pictures:
            print(f"[优化] 正在提取封面并调用 Pingo 压缩...")
            # 将第一张封面图片写入临时文件供 Pingo 使用
            with open(temp_img, "wb") as f:
                f.write(audio.pictures[0].data)
            
            # 调用 Pingo (静默执行，stdout/stderr 重定向到空设备)
            subprocess.run([PINGO_EXE, "-lossless", "-s4", temp_img], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 重新读入压缩后的二进制数据并更新标签
            if os.path.exists(temp_img):
                with open(temp_img, "rb") as f:
                    new_data = f.read()
                
                new_pic = Picture()
                new_pic.data = new_data
                new_pic.type = 3  # 封面类型: Front Cover
                new_pic.mime = "image/jpeg"
                
                # 清除旧图并保存新图（Mutagen 直接操作二进制，不经过控制台）
                audio.clear_pictures()
                audio.add_picture(new_pic)
                audio.save()
                
                if os.path.exists(temp_img):
                    os.remove(temp_img)
                print(f"[成功] 封面图片优化完成。")

        # --- 步骤 2: 备份并使用 flac.exe 重编码音频流 (Level 6) ---
        print(f"[修复] 正在重构音频流并清除冗余数据...")
        if orig_bak.exists():
            orig_bak.unlink()
        
        # 物理改名备份
        f_path.rename(orig_bak)

        # 构建 flac.exe 命令
        cmd_flac = [
            FLAC_EXE, "-6", "-f", "--preserve-modtime",
            str(orig_bak.name), "-o", str(f_path.name)
        ]
        
        # 核心修正：完全不捕获输出，彻底杜绝 UnicodeDecodeError (GBK) 导致的崩溃
        result = subprocess.run(cmd_flac, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if result.returncode == 0:
            print(f"[成功] FLAC 结构修复完成。")
            # 如果需要修复后自动删除备份，可以取消下行的注释
            # orig_bak.unlink()
        else:
            print(f"[失败] flac.exe 重编过程中断，返回码: {result.returncode}")
            # 如果新文件未生成，尝试还原备份
            if not f_path.exists() and orig_bak.exists():
                orig_bak.rename(f_path)

    except Exception as e:
        print(f"[报错] 处理失败: {e}")
        # 异常情况下回滚文件名
        if orig_bak.exists() and not f_path.exists():
            orig_bak.rename(f_path)

if __name__ == "__main__":
    # 检查必要工具是否存在
    for tool in [FLAC_EXE, PINGO_EXE]:
        if not os.path.exists(tool):
            print(f"错误: 无法在 libs 目录下找到工具: {os.path.basename(tool)}")
            sys.exit(1)

    # 处理拖入的文件
    files = sys.argv[1:]
    if not files:
        print("提示: 请将 FLAC 文件拖放到此脚本上进行处理。")
    else:
        for f in files:
            if f.lower().endswith(".flac"):
                process_flac_fix_mutagen(f)
            else:
                print(f"[跳过] 非 FLAC 文件: {os.path.basename(f)}")
    
    input("\n所有任务处理完毕，按回车退出...")