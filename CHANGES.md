# NTEUID 兼容性修复记录

## 背景

KimigaiiWuyi/gsuid_core v0.10.5（当前使用的后端）的 `Bot.send()` 和 `Bot.send_option()`
**不支持**以下参数（这些参数只存在于 Genshin-bots 上游新版本中）：

| 方法 | 不支持的参数 |
|------|-------------|
| `Bot.send_option()` | `at_sender` |
| `Bot.send()` | `wait_recall` |

## 修复的 Bug

### Bug 1：`send_option()` 传了不支持的 `at_sender` 参数

**报错信息：**
```
Bot.send_option() got an unexpected keyword argument 'at_sender'
```

**根因：** 提交 `cdbdd0a`（🐛 修复按钮消息群内丢@）在 5 处 `send_option()` 调用上加上了
`at_sender=bool(ev.group_id)`，但当前 gsuid_core 版本不支持该参数。

**修改方式：** 将 `at_sender` 改为在消息内容中嵌入 `MessageSegment.at(ev.user_id)`，
通过列表形式 `[MessageSegment.at(ev.user_id), 消息文本]` 传递给 `send_option()`。

#### 修改的文件

**1. `nte_sign/__init__.py`** — 签到

```diff
+from gsuid_core.segment import MessageSegment

-await bot.send_option(f"{TITLE}{msg}", sign_buttons(), at_sender=bool(ev.group_id))
+content = [MessageSegment.at(ev.user_id), f"{TITLE}{msg}"] if ev.group_id else f"{TITLE}{msg}"
+await bot.send_option(content, sign_buttons())
```

**2. `nte_ai/tools.py`** — AI 签到

```diff
+from gsuid_core.segment import MessageSegment

-await bot.send_option(f"{TITLE}{result}", sign_buttons(), at_sender=bool(ev.group_id))
+content = [MessageSegment.at(ev.user_id), f"{TITLE}{result}"] if ev.group_id else f"{TITLE}{result}"
+await bot.send_option(content, sign_buttons())
```

**3. `nte_role/role_service.py`** — 角色查询（未登录提示）

```diff
-await bot.send_option(f"{TITLE}{msg}", buttons, at_sender=bool(ev.group_id))
+content = [MessageSegment.at(ev.user_id), f"{TITLE}{msg}"] if ev.group_id else f"{TITLE}{msg}"
+await bot.send_option(content, buttons)
```

**4. `nte_login/bind_service.py`** — 查看绑定 & 切换绑定（2处）

```diff
+from gsuid_core.segment import MessageSegment

-await bot.send_option(f"{TITLE}{msg}", switch_buttons(), at_sender=bool(ev.group_id))
+await bot.send_option(
+    [MessageSegment.at(ev.user_id), f"{TITLE}{msg}"] if ev.group_id else f"{TITLE}{msg}",
+    switch_buttons(),
+)

-await bot.send_option(f"{TITLE}{msg}", switched_buttons(), at_sender=bool(ev.group_id))
+await bot.send_option(
+    [MessageSegment.at(ev.user_id), f"{TITLE}{msg}"] if ev.group_id else f"{TITLE}{msg}",
+    switched_buttons(),
+)
```

**5. `nte_login/login_service.py`** — 发送登录链接

```diff
-await bot.send_option("\n".join(lines), login_link_buttons(url), at_sender=at_sender)
+content = [MessageSegment.at(ev.user_id), "\n".join(lines)] if at_sender else "\n".join(lines)
+await bot.send_option(content, login_link_buttons(url))
```

### Bug 2：`send()` 传了不支持的 `wait_recall` 参数

**报错信息：**
```
Bot.send() got an unexpected keyword argument 'wait_recall'
```

**根因：** 提交 `a71ad9b`（✨ 新增角色面板图管理）在 `send()` 调用上传了
`wait_recall=True` 以获取消息 ID 缓存原图，但当前 gsuid_core 版本不支持该参数。

**修改方式：** 移除 `wait_recall=True`，`cache_original_image()` 已兼容 `None` 输入。

#### 修改的文件

**6. `nte_role/role_service.py`** — 角色面板详情

```diff
-message_ids = await bot.send(MessageSegment.image(img), wait_recall=True)
-cache_original_image(message_ids, original_img_path)
+message_ids = await bot.send(MessageSegment.image(img))
+cache_original_image(None, original_img_path)
```

**7. `nte_role/rank_service.py`** — 最强面板排行

```diff
-message_ids = await bot.send(MessageSegment.image(img), wait_recall=True)
-cache_original_image(message_ids, original_img_path)
+message_ids = await bot.send(MessageSegment.image(img))
+cache_original_image(None, original_img_path)
```

## 注意事项

### 1. resource/ 目录

`NTEUID/resource/` 被 `.gitignore` 排除（第 6 行），仓库里不包含该目录。
从仓库复制插件时**必须手动补充** `resource/` 目录：

```bash
git clone --depth=1 https://cnb.cool/tyql688/NteMeta
cp -r NteMeta/* /path/to/NTEUID/NTEUID/resource/
```

缺少此目录会导致：
- 资源更新命令「下载全部资源」首次安装超时（无 `.git` 目录，走 git fetch）
- 角色查询报"未找到该角色"（无 `char_meta.json`，无法解析角色名）

### 2. Python 字节码缓存

替换文件后必须删除 `__pycache__` 目录，否则 Python 仍运行旧代码：

```bash
find /path/to/plugins/nteuid -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

### 3. 文件列表（共 6 个文件，7 处修改）

| # | 文件 | 修改类型 |
|---|------|---------|
| 1 | `nte_sign/__init__.py` | 新增导入 + 修改调用 |
| 2 | `nte_ai/tools.py` | 新增导入 + 修改调用 |
| 3 | `nte_role/role_service.py` | 修改调用（2处：send_option + send） |
| 4 | `nte_role/rank_service.py` | 修改调用 |
| 5 | `nte_login/bind_service.py` | 新增导入 + 修改调用（2处） |
| 6 | `nte_login/login_service.py` | 修改调用 |

### 4. 兼容性

- 群聊中 `MessageSegment.at()` 实现 @ 提及，与 `at_sender=True` 效果一致
- 私聊中 `ev.group_id` 为假，不走 `MessageSegment.at()`，正常发送纯文本
- `cache_original_image(None, ...)` 内部直接 return，**原图缓存功能降级为空操作**，不影响面板图片展示
