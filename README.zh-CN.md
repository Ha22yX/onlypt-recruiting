# onlyPT Recruiting

[English](README.md) | [线上示例](https://onlypt.rosebeg.com/)

onlyPT Recruiting 是一个可复用的 Flask 网站系统，适用于聚焦招聘、咨询、专业服务和垂直获客类网站。当前公开内容是为 Physical Therapy 招聘业务编写的，但代码结构有意设计成可复用形态，因此同一个项目也可以服务其他具备类似需求的服务型业务：精致的公开官网、可编辑的营销文案、线索捕获、后台审核、邮件通知和轻量部署。

![onlyPT Recruiting 首页预览](static/img/readme-preview.png)

## 这个项目是什么

这不只是一个静态落地页。它是一个带小型 CMS 的业务官网，可以复用于很多相似场景：

- 招聘机构收集雇主和候选人咨询。
- 医疗、法律、金融、教育或 B2B 服务公司需要一个高质感营销网站。
- 顾问和精品服务商希望编辑页面内容，但不想引入大型 CMS。
- 线索获客网站需要保存、查看并通过邮件发送联系表单提交。
- 单品牌或单服务网站需要在多个页面之间保持一致的视觉设计。

默认文案、导航和标签是为 `onlyPT` 编写的，但几乎所有可见文字都可以在后台编辑器中修改。

## 线上示例

生产示例站点位于 [https://onlypt.rosebeg.com/](https://onlypt.rosebeg.com/)。

可以用它预览：

- 公开营销页面。
- 桌面端和移动端响应式布局。
- 持久化全站背景体验。
- 联系表单流程和动画反馈弹窗。
- 项目的整体视觉方向。

## 核心功能

- Home、Employers、Therapists、About 和 Contact 公共页面。
- 后台内容编辑器，可编辑页面文案、导航文字、页脚文字、元信息和联系页消息。
- 编辑内容时可通过后台 iframe 实时预览。
- 可编辑全站背景图。
- 可编辑 favicon / 浏览器标签页图标。
- 可从后台调整首个页面区块的垂直偏移。
- 联系表单带成功/错误动画反馈弹窗。
- 线索保存到 `instance/leads.csv`。
- 后台线索收件箱位于 `/admin/leads`。
- 每条线索支持跟进状态、下一步、备注和时间戳。
- 通过 Zoho 或其他已配置 SMTP 服务发送线索邮件通知。
- 带全站发送频率控制的邮件通知队列。
- 联系表单提交限制：
  - 同一 IP：10 分钟最多 3 次提交。
  - 同一邮箱地址：1 小时最多 5 次提交。
  - 全站邮件发送：每分钟最多 2 封，超出部分进入队列。
- 可选 Twilio WhatsApp 线索通知。
- 同源站内导航会保持共享背景不重新加载。
- 运行时上传文件和内容覆盖保存在 `instance/`，不进入 Git。

## 复用于其他网站

这个项目适合任何具备相同基本结构的网站：

1. 一个包含 4-6 个核心页面的公开营销网站。
2. 一个联系表单或线索表单。
3. 一个用于内容编辑和线索查看的私有后台。
4. 邮件通知发送能力。
5. 一套一致的品牌视觉系统。

要适配另一个业务：

1. 在后台内容编辑器中修改公开文案。
2. 在 `General` 中替换背景图和 favicon。
3. 更新导航标签、页脚标签、元信息和联系方式文字。
4. 在 `Email Notifications` 中配置 SMTP 通知设置。
5. 只有当新业务需要不同页面结构，而不只是不同文字时，才更新模板。

对于大多数同类型服务网站，不需要重写应用。后台 CMS 字段和模板已经足够完成品牌和内容调整。

## 技术栈

- Python + Flask。
- Jinja 模板。
- 原生 CSS 和 JavaScript。
- `instance/` 下的 CSV/JSON 文件存储。
- 使用 Python `smtplib` 发送 SMTP 邮件通知。
- 可选 Twilio WhatsApp API。

项目不要求数据库。这让它很容易部署到 VPS、PaaS 或基于面板的 Linux 服务器。

## 本地开发

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

打开：

```text
http://127.0.0.1:5000
```

## 环境变量

生产环境必须设置安全值。如果缺少 `ONLYPT_ADMIN_PASSWORD`，后台登录会被禁用，而不是回退到默认密码。

```text
SECRET_KEY=replace-with-a-long-random-secret
ONLYPT_ADMIN_USERNAME=admin
ONLYPT_ADMIN_PASSWORD=replace-with-a-strong-password
```

可选 WhatsApp 通知变量：

```text
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+15551234567
```

## 后台面板

打开：

```text
/admin/login
```

登录后：

- `/admin/content/home` 编辑站点内容。
- `/admin/leads` 查看提交的线索。
- `General -> Background` 管理全站背景。
- `General -> Page Tab` 管理 favicon。
- `General -> Layout` 控制首个页面区块的起始偏移。
- `Email Notifications` 管理 SMTP 设置。

默认开发凭据定义在 `app.py` 中，但生产环境应该通过环境变量覆盖。

## 邮件通知

联系表单提交会先保存，然后尝试发送通知。

邮件设置在后台中管理：

- 通知收件人。
- 开启/关闭邮件通知。
- 发件邮箱和发件显示名称。
- SMTP 主机、端口、安全模式、用户名和密码。

当前生产配置使用 Zoho SMTP。其他支持认证 SMTP 的服务商也可以使用。

### 频率控制和队列

为了避免 SMTP 频率限制：

- 站点每分钟最多发送 2 封通知邮件。
- 额外通知会写入 `instance/email_queue.json`。
- cron 或其他定时 worker 应该每分钟调用一次 `process_email_queue()`。
- 队列中发送失败的消息会按退避策略重试，并在多次失败后标记为失败。

示例 cron 命令：

```cron
* * * * * cd /path/to/project && flock -n /tmp/onlypt-email-queue.lock /path/to/venv/bin/python -c "from app import process_email_queue; process_email_queue()" >> /path/to/instance/email_queue_cron.log 2>&1
```

## 联系表单限制

联系表单包含服务端限制：

- 同一 IP：10 分钟最多 3 次提交。
- 同一邮箱：1 小时最多 5 次提交。

当访问者超过限制时，站点会显示动画错误弹窗，并且不会保存另一条重复线索。

## 运行时数据

运行时文件存储在 `instance/` 中，不应提交：

```text
instance/content_overrides.json    CMS 内容覆盖
instance/leads.csv                 联系表单提交
instance/lead_threads.json         线索状态和备注
instance/submission_limits.json    联系表单提交频率状态
instance/email_rate.json           邮件发送频率状态
instance/email_queue.json          排队中的通知邮件
instance/notification_errors.log   邮件/Twilio 发送错误
instance/uploads/                  背景图和 favicon 上传文件
```

## 项目结构

```text
app.py                 Flask 应用、路由、CMS 辅助函数、线索逻辑、邮件队列
templates/            公开页面和后台模板
static/css/           公开页面和后台样式
static/js/            公开导航/交互和后台编辑器逻辑
static/img/           静态图片资源
instance/             运行时数据、上传、内容覆盖、线索
requirements.txt      Python 依赖
```

## 部署说明

推荐生产部署方式：

1. 运行在 Nginx 或其他反向代理后面。
2. 使用 Gunicorn 或其他 WSGI 服务器运行 Flask。
3. 将应用部署到一个固定项目目录，例如 `/www/wwwroot/onlypt.rosebeg.com/current`。
4. 在这个固定目录里使用 Git 做代码版本控制、更新和回滚，例如 `git pull`、`git reset` 或切换到指定提交。
5. 保持 `instance/` 持久化并且不要提交到源码仓库。它可以是实体目录，也可以软链接到共享数据目录。
6. 如果使用宝塔这类面板，面板项目根目录应直接指向固定目录，而不是 `current -> releases/...` 软链接，这样进程状态检测和启动/停止操作才能和真实运行服务一致。
7. 通过环境变量设置强后台凭据。
8. 在后台面板中配置 SMTP。
9. 为 `process_email_queue()` 添加定时队列 worker。
10. 定期备份 `instance/`。

项目不再需要 release 目录部署。Git 仍然是源码版本控制系统；运行时数据仍然保存在 `instance/` 中。

不要提交：

- `instance/`
- `.env`
- 虚拟环境
- 部署归档文件或临时服务器备份
- 用户上传资源

## 定制指南

大部分修改不需要改代码：

- 品牌名和副标题：Admin -> General。
- 导航和页脚标签：Admin -> General。
- 页面文案：Admin -> Home / Employers / Therapists / About / Contact。
- 背景图：Admin -> General -> Background。
- Favicon：Admin -> General -> Page Tab。
- 联系通知邮箱：Admin -> Email Notifications。

只有这些情况通常需要改代码：

- 需要新增页面区块。
- 想要不同的表单字段。
- 需要不同的线索工作流。
- 想用数据库存储替代 CSV/JSON。
- 需要集成 CRM 或外部自动化平台。

## 授权 / 所有权

该仓库是 source-available 项目，不是开源项目。

代码可以用于查看、学习、fork，以及个人、教育、审阅或非商业内部评估目的下的私有修改。

未经仓库所有者事先书面许可，不得将本项目用于商业部署、付费客户项目、销售、转售、SaaS 托管、模板销售、竞争性招聘/人力资源产品、闭源衍生作品，或其他任何商业变现用途。

完整条款请查看 [LICENSE](LICENSE) 中的 onlyPT Source Available Non-Commercial License。
