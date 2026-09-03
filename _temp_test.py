with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = 'TITLEBAR_JS = """\n'
end_marker = '\n"""\n'
start_idx = content.find(start_marker) + len(start_marker)
end_idx = content.find(end_marker, start_idx)
old_js = content[start_idx:end_idx]

# 在 inject() 调用之前加模拟拖动测试
old_inject = '''    inject();
})();'''

new_inject = '''    // [TEMP-TEST] 页面加载3秒后模拟在标题栏区域的拖动
    setTimeout(function() {
        debugLog('模拟拖动测试开始');
        var evt1 = new PointerEvent('pointerdown', {
            button: 0, buttons: 1, clientX: 100, clientY: 16,
            screenX: 900, screenY: 500, pointerId: 1, pointerType: 'mouse',
            bubbles: true, cancelable: true
        });
        window.dispatchEvent(evt1);

        setTimeout(function() {
            var evt2 = new PointerEvent('pointermove', {
                button: 0, buttons: 1, clientX: 200, clientY: 16,
                screenX: 1000, screenY: 500, pointerId: 1, pointerType: 'mouse',
                bubbles: true, cancelable: true
            });
            window.dispatchEvent(evt2);

            setTimeout(function() {
                var evt3 = new PointerEvent('pointerup', {
                    button: 0, buttons: 0, clientX: 200, clientY: 16,
                    screenX: 1000, screenY: 500, pointerId: 1, pointerType: 'mouse',
                    bubbles: true, cancelable: true
                });
                window.dispatchEvent(evt3);
                debugLog('模拟拖动测试结束');
            }, 200);
        }, 200);
    }, 3000);

    inject();
})();'''

if old_inject in old_js:
    old_js = old_js.replace(old_inject, new_inject, 1)
    print("OK: 已加模拟拖动测试")
else:
    print("FAILED: 未找到 inject()")

content = content[:start_idx] + old_js + content[end_idx:]
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
