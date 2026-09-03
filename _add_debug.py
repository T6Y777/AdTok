with open('AdTok.py', 'r', encoding='utf-8') as f:
    code = f.read()

old = '''    def on_loaded():
        css_json = json.dumps(TITLEBAR_CSS)'''

new = '''    def on_loaded():
        print("DEBUG: on_loaded called", flush=True)
        css_json = json.dumps(TITLEBAR_CSS)'''

if old in code:
    code = code.replace(old, new, 1)
    print("OK: 添加调试输出")
else:
    print("FAILED: 未找到目标")
    # 尝试用行号
    lines = code.split('\n')
    for i, line in enumerate(lines):
        if 'def on_loaded():' in line:
            print(f"找到 on_loaded 在第 {i+1} 行: {repr(line)}")
            print(f"下一行: {repr(lines[i+1])}")
            lines.insert(i+1, '        print("DEBUG: on_loaded called", flush=True)')
            break
    code = '\n'.join(lines)
    print("OK: 通过行号添加调试输出")

with open('AdTok.py', 'w', encoding='utf-8') as f:
    f.write(code)
