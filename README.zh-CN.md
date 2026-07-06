# onlyPT Recruiting

[English](README.md) | [线上示例](https://onlypt.rosebeg.com/)

onlyPT Recruiting 是一个可复用的 Flask 官网系统。当前内容是为 Physical Therapy 招聘场景定制的，但项目本身并不局限于 onlyPT。所有同类型需求的网站都可以基于这个项目快速搭建：精品服务型官网、招聘/咨询业务官网、垂直行业获客页、带后台内容编辑和线索管理的小型商业网站。

![onlyPT Recruiting 首页预览](static/img/readme-preview.png)

## 项目定位

这不是一个简单的静态落地页，而是一个带轻量 CMS、线索收集、邮件通知和后台管理能力的业务官网项目。

它适合这些场景：

- 招聘机构收集雇主和候选人咨询。
- 医疗、法律、金融、教育、B2B 服务公司的品牌官网。
- 顾问、咨询师、精品工作室、垂直服务商的获客网站。
- 需要联系表单、线索保存、后台查看、邮件提醒的网站。
- 希望不接入大型 CMS，但又能让运营人员编辑页面文案的网站。

默认文案和页面命名是 onlyPT 招聘业务，但绝大多数前台文字都可以在后台改掉。因此，这个仓库可以作为同类服务型网站的通用基础项目。

## 线上示例

示例站点：

```text
https://onlypt.rosebeg.com/
```

可以用它查看：

- 首页、雇主页、治疗师页、关于页、联系页。
- 桌面端和移动端响应式布局。
- 全站共用背景和页面切换体验。
- 联系表单提交后的弹窗反馈。
- 项目的整体视觉方向。

## 核心功能

- Home、Employers、Therapists、About、Contact 公共页面。
- 后台内容编辑器，可维护页面文案、导航、页脚、SEO 描述和联系页文字。
- 后台实时预览 iframe。
- 后台上传和管理全站背景图。
- 后台上传和管理浏览器标签页图标 favicon。
- 后台滑块调整每个页面第一个板块的起始高度。
- 联系表单提交成功/失败弹窗动画反馈。
- 表单线索保存到 `instance/leads.csv`。
- 后台线索收件箱 `/admin/leads`。
- 每条线索支持状态、下一步、备注和更新时间。
- 支持 SMTP 邮件提醒，目前主设计是通过 Zoho SMTP 或其他 SMTP 服务发送。
- 邮件发送队列，避免短时间触发 SMTP 频率限制。
- 联系表单提交限流：
  - 同一 IP：10 分钟最多 3 次。
  - 同一邮箱：1 小时最多 5 次。
  - 全站邮件发送：每分钟最多 2 封，超过的邮件进入队列。
- 可选 Twilio WhatsApp 线索提醒。
- 站内页面切换时保留全站背景，减少整页刷新带来的割裂感。
- 运行时内容、上传文件和线索数据全部放在 `instance/`，不进入 Git。

## 为什么适合复用

很多服务型网站的结构都很接近：

1. 一个品牌首页。
2. 面向不同受众的服务页面。
3. 关于页或信任背书页。
4. 联系/咨询表单。
5. 后台能改文案。
6. 表单提交后能通知负责人。
7. 后台能查看线索和跟进状态。

onlyPT Recruiting 已经把这些通用能力做好了。要换成另一个业务，通常只需要：

1. 在后台修改品牌名、导航、页面文案和页脚。
2. 上传新的背景图和 favicon。
3. 配置新的 SMTP 收件人和发件账号。
4. 必要时微调页面模板中的区块内容。

如果只是同类型的服务获客网站，大部分情况下不用重写后端。

## 技术栈

- Python + Flask。
- Jinja 模板。
- 原生 CSS 和 JavaScript。
- CSV / JSON 文件存储。
- SMTP 邮件通知。
- 可选 Twilio WhatsApp 通知。

项目不依赖数据库，适合 VPS、宝塔面板、普通 Linux 服务器、PaaS 或轻量云服务器部署。

## 本地开发

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

启动后打开：

```text
http://127.0.0.1:5000
```

## 环境变量

本地开发可以不配置环境变量，但生产环境建议设置安全值。

```text
SECRET_KEY=替换为足够长的随机密钥
ONLYPT_ADMIN_USERNAME=admin
ONLYPT_ADMIN_PASSWORD=替换为强密码
```

可选 WhatsApp 通知：

```text
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+15551234567
```

## 后台入口

后台登录：

```text
/admin/login
```

登录后常用页面：

- `/admin/content/home`：编辑页面内容。
- `/admin/leads`：查看联系表单线索。
- `General -> Background`：管理全站背景图。
- `General -> Page Tab`：管理浏览器标签页图标。
- `General -> Layout`：调整首屏板块起始高度。
- `Email Notifications`：配置邮件通知。

默认开发账号密码写在 `app.py` 中，但生产环境必须通过环境变量覆盖。

## 邮件通知

联系表单提交后，应用会先保存线索，再尝试发送邮件通知。

邮件配置在后台 `Email Notifications` 中维护：

- 是否开启邮件提醒。
- 收件人邮箱。
- 发件人邮箱。
- 发件人显示名称。
- SMTP 主机。
- SMTP 端口。
- SSL / TLS 模式。
- SMTP 用户名和密码。

当前生产环境使用 Zoho SMTP。只要其他邮件服务商支持 SMTP，也可以切换成其他服务商。

### 邮件队列和频率控制

为避免再次触发 SMTP 服务商的频率限制，项目内置了邮件发送节流：

- 全站最多每分钟发送 2 封通知邮件。
- 超出的邮件会写入 `instance/email_queue.json`。
- 队列任务应每分钟执行一次 `process_email_queue()`。
- 队列邮件失败后会延迟重试，超过最大次数后标记失败并写日志。

示例 cron：

```cron
* * * * * cd /path/to/project && flock -n /tmp/onlypt-email-queue.lock /path/to/venv/bin/python -c "from app import process_email_queue; process_email_queue()" >> /path/to/instance/email_queue_cron.log 2>&1
```

## 联系表单限流

为了防止恶意提交或测试时刷爆 SMTP，后端有限流规则：

- 同一 IP：10 分钟最多 3 次提交。
- 同一邮箱：1 小时最多 5 次提交。

超过限制时，用户会看到错误弹窗，系统不会保存重复线索，也不会发送邮件。

## 运行时数据

这些文件都在 `instance/` 目录中，不应该提交到 Git：

```text
instance/content_overrides.json    后台 CMS 内容覆盖
instance/leads.csv                 联系表单线索
instance/lead_threads.json         线索状态和备注
instance/submission_limits.json    表单提交限流状态
instance/email_rate.json           邮件发送频率状态
instance/email_queue.json          邮件队列
instance/notification_errors.log   邮件 / WhatsApp 错误日志
instance/uploads/                  背景图和 favicon 上传文件
```

## 项目结构

```text
app.py                 Flask 应用、路由、CMS、线索、邮件队列
templates/            前台页面和后台模板
static/css/           前台和后台样式
static/js/            前台交互和后台编辑器逻辑
static/img/           静态图片资源
instance/             运行时数据、上传文件、内容覆盖、线索
requirements.txt      Python 依赖
```

## 部署建议

推荐生产部署方式：

1. 使用 Nginx 或其他反向代理。
2. 使用 Gunicorn 或其他 WSGI 服务运行 Flask。
3. 把 `instance/` 放在持久化共享目录。
4. 源码按 release 方式部署。
5. 用环境变量设置强后台密码。
6. 在后台配置 SMTP。
7. 设置每分钟执行一次邮件队列任务。
8. 定期备份 `instance/`。

不要提交这些内容：

- `instance/`
- `.env`
- 虚拟环境
- 部署压缩包
- 用户上传文件

## 定制指南

通常不需要改代码的内容：

- 品牌名和副标题。
- 导航和页脚文字。
- 各页面文案。
- 全站背景图。
- favicon。
- 联系方式和表单提示文字。
- 邮件通知配置。
- 首屏板块起始高度。

可能需要改代码的情况：

- 新增页面。
- 改联系表单字段。
- 新增复杂线索流程。
- 接入 CRM。
- 改成数据库存储。
- 增加支付、会员、预约等业务功能。

## 维护说明

这个项目适合持续作为多个同类型服务网站的基础版本。后续如果要复用到新业务，建议保留通用后端能力，只替换文案、图片、SMTP 配置和必要模板区块，这样维护成本最低。

## 授权 / 所有权

该仓库作为 onlyPT 类型服务网站的可复用项目维护。用于第三方商业部署前，请先与仓库所有者确认授权和使用范围。
