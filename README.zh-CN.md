# onlyPT Recruiting

[English](README.md) | [线上示例](https://onlypt.rosebeg.com/)

![onlyPT Recruiting 首页预览](static/img/readme-preview.png)

onlyPT Recruiting 是一个面向物理治疗师（Physical Therapist, PT）招聘场景的 Flask 网站。它包含公开官网页面和简单的后台 CMS，服务于医疗雇主招聘 PT、以及 PT 从业者了解职业机会这两个核心受众。

## 线上示例

示例网站部署在 [https://onlypt.rosebeg.com/](https://onlypt.rosebeg.com/)。可以通过这个地址查看首页、雇主页、治疗师页、关于页和联系页的实际视觉效果、响应式布局和内容体验。

## 功能

- 面向 Home、Employers、Therapists、About、Contact 的响应式营销页面。
- 后台内容编辑器，可维护页面文案和全站通用文字。
- 后台可上传并管理全站固定背景图。
- 联系表单会把线索保存到本地 `instance/leads.csv`。
- 支持通过 Twilio WhatsApp 配置发送线索通知。
- 上传文件、运行时内容覆盖和线索数据保存在 `instance/`，不进入源码版本控制。

## 本地开发

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

启动后打开 `http://127.0.0.1:5000`。

## 后台

打开 `/admin/login` 登录后台，然后进入 `/admin/content/home` 编辑页面内容。

默认后台账号和密码来自环境变量：

```text
ONLYPT_ADMIN_USERNAME=admin
ONLYPT_ADMIN_PASSWORD=REDACTED_ADMIN_PASSWORD
```

如果没有配置环境变量，应用会使用代码中的开发默认值。生产环境建议务必通过环境变量设置安全密码。

全站背景图编辑入口在 `General -> Background`。上传新背景图时，会自动替换之前的背景图；公开站点会在所有页面使用同一张固定背景图。

## WhatsApp 线索通知

联系表单提交会保存到 `instance/leads.csv`。如果配置了以下环境变量，应用还会通过 Twilio 发送 WhatsApp 通知：

```text
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+15551234567
```

`TWILIO_WHATSAPP_FROM` 必须是 Twilio 支持 WhatsApp 的发送方。使用 Sandbox 测试时，需要使用 Twilio 的 Sandbox 发送号码，并确保接收号码已经加入 Sandbox。

## 项目结构

```text
app.py                 Flask 路由、CMS 辅助函数、上传处理
templates/            公开页面和后台页面模板
static/css/           公开页面和后台样式
static/js/            公开页面交互和后台编辑器逻辑
static/img/           站点图片资源和 README 预览图
instance/             运行时数据、上传、内容覆盖、线索
```

## 部署说明

生产部署建议把运行时数据放在共享的 `instance/` 目录中，并以 release 方式部署源码。不要提交 `instance/`、`.env`、虚拟环境或部署压缩包。
