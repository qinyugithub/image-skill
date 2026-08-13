# Chat Comic Generator

一个在 ChatGPT/Codex 对话中使用的水彩单幅漫画生成 Skill。

你只需要提供“画面内容”和“底部文案”，Skill 会先通过内置图片生成能力制作无字水彩插画，再使用本地排版脚本准确加入中文文案，最终输出一张 800×1200 的 PNG 漫画。

## 主要特点

- 不需要 OpenAI API Key，直接使用 ChatGPT/Codex 内置图片生成能力。
- 参考仓库内置样图，稳定生成白底、黑色手绘墨线、透明水彩风格的单幅漫画。
- 插画生成与文字排版分离，避免图片模型写错中文。
- 默认使用内置 Ma Shan Zheng（马善政）排版中文，使用适度加粗的书写笔画。
- 优先使用较大字号；一行放不下时自动增加到最多 5 行，使用紧凑行距并利用底部安全区域，同时避免拆开常用词组。
- 按字体基线渲染整行文字，使逗号、句号等标点自然位于每行靠下位置。
- 保留用户原始文案，只调整换行，不擅自改写字词或标点。
- 自动保存任务定义、无字插画、最终成品和校验记录。
- 支持 `daily`、`poetic`、`metaphor`、`vivid` 四种风格组。

## 安装方法

### 方法一：安装到当前项目

将仓库克隆到项目的 `.codex/skills/chat-comic-generator`：

```powershell
git clone https://github.com/qinyugithub/image-skill.git .codex/skills/chat-comic-generator
```

目录结构应类似：

```text
项目目录/
└── .codex/
    └── skills/
        └── chat-comic-generator/
            ├── SKILL.md
            ├── agents/
            ├── assets/
            ├── references/
            └── scripts/
```

### 方法二：安装为个人 Skill

将仓库克隆到个人 Codex Skill 目录。在 Windows 中通常为：

```powershell
git clone https://github.com/qinyugithub/image-skill.git "$env:USERPROFILE\.codex\skills\chat-comic-generator"
```

安装后重新打开一个 Codex 任务，使 Skill 被重新发现。

## 最简单的使用方法

在 ChatGPT/Codex 对话框中直接发送：

```text
使用 $chat-comic-generator 生成同风格漫画

画面内容：空荡的新房间里，一个人站在窗边，窗台上只放着一盆新买的绿植。

底部文案：不是所有关系都值得挽留。有些人的离开，不是遗憾，而是生活替你腾出了位置
```

随后 Skill 会自动完成：

1. 根据内容选择合适的风格组。
2. 从对应风格组中选取 3 张参考图。
3. 生成下方留白的无字水彩插画。
4. 优先在句号等语义边界处自动换行，以更大的字号排版，但不修改原文。
5. 将中文准确排入留白区域。
6. 检查图片尺寸、文字、留白和文件完整性。
7. 在对话中展示最终图片并提供下载路径。

## 推荐输入格式

### 基础格式

```text
使用 $chat-comic-generator 生成同风格漫画

画面内容：<希望漫画呈现的画面>

底部文案：<需要逐字保留的中文文案>
```

### 带可选设置的格式

```text
使用 $chat-comic-generator 生成同风格漫画

画面内容：一个人坐在深夜的窗边，桌上放着一部没有新消息的手机。

底部文案：
生活不会因为你着急，
就提前给你答案。
很多事情，熬过去以后，
才知道当初没那么可怕

风格组：poetic
情绪：安静、克制、略带孤独
强调色：灰蓝色
不要出现：其他人物、文字、Logo、水印
```

如果你已经手动分行，Skill 会明确标记并保留这些换行；某一行仍然过长时可继续拆分。如果只提供一整段文案，Skill 会优先保持较大的字号，并可重新均衡整段原文，按语义自动分成最多 5 行。

## 风格组说明

| 风格组 | 适用内容 | 画面特点 |
| --- | --- | --- |
| `daily` | 日常生活、职场、动物拟人、轻微冷幽默 | 单主体、少量道具、浅蓝或灰紫强调色 |
| `poetic` | 孤独、成长、风景、内心感受、温柔文案 | 人物较小、色彩柔和、留白更多 |
| `metaphor` | 压力、选择、人生道理、抽象概念 | 中心符号配小人物，视觉隐喻直接 |
| `vivid` | 儿童、动物闹剧、手机、贪吃、高能量幽默 | 色彩更鲜艳，造型更夸张 |

不指定时默认使用 `daily`。当内容明显偏诗意、视觉隐喻或高饱和童趣时，Skill 会自动切换到更合适的风格组。

## 输出文件

每次生成都会建立独立任务目录：

```text
output/comics/jobs/<时间>-<任务标识>/
├── job.json
├── prompt.txt
├── illustration.png
├── final.png
└── final.manifest.json
```

- `job.json`：画面、文案、风格和参考图等任务信息。
- `prompt.txt`：用于生成无字插画的提示词。
- `illustration.png`：未加入中文的原始插画。
- `final.png`：最终的 800×1200 漫画。
- `final.manifest.json`：字体、排版、图片哈希等校验记录。

默认字体文件位于 `assets/fonts/MaShanZheng-Regular.ttf`，来源于 Google Fonts，并按同目录 `MaShanZheng-OFL.txt` 中的 SIL Open Font License 1.1 分发。仍可通过 `--font`、`COMIC_FONT_PATH` 或任务字体设置覆盖默认字体。

生成历史默认保留，方便之后只修改文案排版或重新生成插画。

## 使用建议

- 画面内容尽量只描述一个瞬间、一个动作或一个视觉隐喻。
- 道具越少，越容易保持仓库样图的大面积白底和克制感。
- 底部文案推荐 2～5 行，每行尽量不超过 10～14 个汉字。
- 想稳定保持系列感时，可固定使用同一个风格组和强调色。
- 如果只想修改文案，应明确说明“保留插画，只重新排版文字”。
- 如果只想修改画面，应明确说明“保持文案不变，重新生成无字插画”。

## 常见问题

### 是否需要 API Key？

不需要。默认工作流只使用 ChatGPT/Codex 内置图片生成能力，不调用 OpenAI API。

### 为什么不直接让图片模型生成中文？

图片模型可能写错字、漏字或产生伪文字。本 Skill 先生成完全无字的插画，再由本地脚本确定性排版中文，从而保证文案准确。

### 可以改变最终尺寸吗？

当前标准样固定为 800×1200 PNG，以保持与内置参考漫画一致。如果需要其他尺寸，应同步调整排版脚本和验收规则。

### 为什么没有触发 Skill？

请确认目录名为 `chat-comic-generator`，目录内存在 `SKILL.md`，并在新任务中明确写出：

```text
使用 $chat-comic-generator 生成同风格漫画
```

## 仓库地址

<https://github.com/qinyugithub/image-skill>
