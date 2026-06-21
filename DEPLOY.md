# 部署到公网

现在本地运行的 `http://127.0.0.1:8501/` 只能在你的电脑上访问。要让其他玩家也能打开，需要把这个 Streamlit App 部署到公网平台。

## 推荐方案：Streamlit Community Cloud

这个项目没有数据库、没有登录、没有后端服务依赖，最适合先用 Streamlit Community Cloud 做公开 Demo。

部署步骤：

1. 在 GitHub 创建一个新仓库，例如 `ba-team-recommender`。
2. 把本目录里的文件推到仓库根目录，确保仓库里直接能看到：

```text
app.py
recommender.py
requirements.txt
README.md
data/characters.json
scripts/update_from_gamekee.py
```

3. 打开 `https://share.streamlit.io/`，用 GitHub 登录。
4. 点击 `Create app`。
5. 选择你的 GitHub 仓库、分支和入口文件：

```text
app.py
```

6. 点击 `Deploy`。部署完成后会得到一个类似下面的公网链接：

```text
https://你的应用名.streamlit.app/
```

这个链接发给别人后，别人就能直接使用网页。

## GitHub 推送示例

如果这是一个新仓库，可以在本目录执行：

```bash
git init
git add .
git commit -m "Initial Blue Archive team recommender"
git branch -M main
git remote add origin https://github.com/你的用户名/ba-team-recommender.git
git push -u origin main
```

如果你已经有仓库，只需要把当前文件提交并推送即可。

## 另一个选择：Hugging Face Spaces

也可以用 Hugging Face Spaces：

1. 新建 Space。
2. SDK 选择 `Streamlit`。
3. 上传本项目文件。
4. 确保 `requirements.txt` 存在，并且入口文件是 `app.py`。

Hugging Face 更适合以后加入模型、向量检索或 AI 推荐时继续扩展。

## 当前项目是否适合公开部署

当前版本适合公开 Demo，因为：

- 依赖很少，只有 Streamlit。
- `characters.json` 约 836 KB，适合随代码一起部署。
- “我的 Box”目前只存在用户浏览器会话中，不会写入服务器数据库。
- 导入的 Box JSON 只用于当次页面交互，当前代码没有保存玩家个人数据。

公开前建议注意：

- 保留 README 中的数据来源说明。
- 如果后续继续使用 GameKee / SchaleDB 的资料公开展示，最好补充更明确的来源链接和免责声明。
- 不要在公开仓库提交 `.streamlit/secrets.toml`、账号 Cookie、API Key 或任何私人文件。

## 以后升级成真正线上产品

当用户量变多或要做账号系统时，可以再考虑：

- 用户账号和 Box 云端保存：Supabase、Firebase 或 PostgreSQL。
- 定时同步角色数据：GitHub Actions 或后台任务。
- 自定义域名：Streamlit Cloud、Render、Fly.io 或 VPS + Nginx。
- 数据授权和免责声明页面。
