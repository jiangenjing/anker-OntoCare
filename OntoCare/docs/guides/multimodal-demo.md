# 模型与多模态 Demo 接入

运行 `bash run.sh`，打开启动信息中的本机地址，在客服导航进入“模型与多模态”。当前演示进程地址：http://127.0.0.1:5187/models.html 。

- 网关：https://ai-router-cn-pub.anker-in.com
- 主客服文字：hackathon/v_model/nova-pro
- 主客服照片：hackathon/v_model/deepseek-v4.1-flash
- 九个模型使用交接包原适配器；能力页提供文字、图片理解、Nova 视频直传、ASR、TTS、Seedream。
- 文字、图片和视频：/chat/completions
- ASR：/openai_passthrough/services/aigc/multimodal-generation/generation
- TTS：/openai_passthrough/services/audio/tts/SpeechSynthesizer
- 图片生成：/v1/images/generations
- 语音头：`x-model-provider: dashscope_ audio`，内部空格保留。

## 密钥

在本机能力页输入比赛 Key，点击“应用到整个 Demo”，同时更新主客服文字与照片调用；密钥只在服务器内存，不回显，不进入浏览器存储。重启需重新填写。持久配置可在 `.env.local` 设置 `COMPETITION_API_KEY`，留空 LLM_API_KEY 和 VISION_API_KEY 时两者使用该比赛密钥。旧服务商配置保存在本机 `.env.previous-provider.local`，不进入交付 ZIP。

## 多模态边界

能力页图片最多3MB，Nova MP4直传最多16MB；ASR前在浏览器将可解码音频转换为16kHz单声道WAV，最长120秒。文字结果可复制回客服，核对型号和知识后继续办理。此处没有自动将独立模型输出写成已确认售后证据。原客服上传入口仍保留原有抽帧证据处理路径，不等同于能力页的视频直传。视频音轨尚未自动串联ASR。

## 验证

原有203个Python测试通过；新增5个测试验证共享配置、不回传密钥、本机与跨来源访问限制、缺密钥状态、文字请求路径和TTS精确请求头。前端脚本语法检查通过，浏览器确认页面正常显示。

当前没有比赛 Key，未对任何模型声称线上调用成功。输入 Key 后逐项发送任务，根据返回状态与内容验证实际权限和网关能力。本机配置接口不适用于直接公开部署；公开部署应接入管理员鉴权。
