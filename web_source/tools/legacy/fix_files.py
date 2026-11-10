import os, re

base = r"H:\中国国际大学生创新创业计划\ui\frontend\src\views"
filepath = os.path.join(base, "DashboardLayout.vue")

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix only the import line
old_import = 'import { PeopleOutline, CubeOutline, SettingsOutline, ChevronBack, ChevronForward, ArrowBack }'
content = content.replace(
    'import { PeopleOutline, CubeOutline, 设置Outline, ChevronBack, ChevronForward, ArrowBack }',
    old_import
)

# Put Chinese labels back in menu options (they were reverted to English)
content = content.replace(
    '{ label: "Settings", key:',
    '{ label: "设置", key:'
)
content = content.replace(
    '{ label: "Patient List", key:',
    '{ label: "患者列表", key:'
)
content = content.replace(
    '{ label: "Model Manager", key:',
    '{ label: "模型管理", key:'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("DashboardLayout fixed properly")