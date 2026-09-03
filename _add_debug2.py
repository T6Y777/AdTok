with open('AdTok.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'def on_loaded():' in line:
        print(f"找到 on_loaded 在第 {i+1} 行")
        # 插入调试输出
        debug_line = '        with open(r"D:\\AdTok\\debug_onloaded.txt", "w") as f: f.write("on_loaded called\\n")\n'
        lines.insert(i+1, debug_line)
        print("OK: 插入文件写入调试")
        break

with open('AdTok.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("完成！")
