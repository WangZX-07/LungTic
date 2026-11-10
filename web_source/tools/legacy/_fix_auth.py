path = r'H:\\中国国际大学生创新创业计划\\ui\\backend\\routers\\auth.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the bad f-string around line 378 and fix it
fixed = []
for line in lines:
    # Replace the problematic multi-line f-string that has literal backtick-n
    if 'body = f"' in line and "req.username" in line and "\x60n" in line:
        # Replace with a proper multi-line plain string
        indent = line[:len(line) - len(line.lstrip())]
        fixed.append(indent + 'body = ("您好 " + req.username + "，\\n\\n"\n')
        fixed.append(indent + '        "您的 LungTic 账号已创建成功！\\n\\n"\n')
        fixed.append(indent + '        "用户名：" + req.username + "\\n"\n')
        fixed.append(indent + '        "密码：" + req.password + "\\n"\n')
        fixed.append(indent + '        "角色：" + req.role + "\\n\\n"\n')
        fixed.append(indent + '        "请登录后及时修改密码。\\n"\n')
        fixed.append(indent + '        "LungTic Team")\n')
        # Skip original subsequent lines until we find a closing )
        continue
    fixed.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(fixed)

import ast
with open(path, 'r', encoding='utf-8') as f:
    ast.parse(f.read())
print('auth.py OK')