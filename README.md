# The Pearl — 自进化客服 Agent Demo

> 家电电商智能客服演示，5 分钟展示「人工纠正 → 经验提炼 → 下次复用」的完整闭环。

## 准备工作（一次性）

电脑上需要已安装：

- **Python 3.10+**：终端输入 `python3 --version` 确认
- **Node.js 18+**：终端输入 `node --version` 确认

## 启动步骤（4 步）

```bash
# 1. 进入项目
cd the-pearl-demo

# 2. 创建虚拟环境并安装 Python 依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. 安装 Node 依赖
npm install

# 4. 配置环境变量并启动
cp .env.example .env
streamlit run app.py
```

浏览器会自动打开，或手动访问 **http://localhost:8501**。

## 演示剧本

| 步骤 | 操作 | 你要说什么 |
|------|------|------------|
| 1 | 页面加载，看到「客户咨询」区域 | "这是一个家电客服 Agent，客户提问后它会给出回答" |
| 2 | 输入「洗衣机脱水时一直乱跳，是不是坏了」点发送 | "你看，它给了个比较笼统的回答，没有排查顺序和安全边界" |
| 3 | 点「标记为值得进化」 | "我们觉得这个回答不够好，标记它需要改进" |
| 4 | 在右侧人工纠正区补充排查步骤 | "补充了运输螺栓、地面脚垫、衣物偏载的排查顺序，以及停用转人工的边界" |
| 5 | 点「生成候选 Capsule」-点「批准」 | "经验被提炼成一个可复用的知识单元" |
| 6 | 输入相似问题「洗衣机一脱水就晃得厉害」 | "同样的问题，回答明显更具体、更安全了" |
| 7 | 展示「进化前后对比」面板 | "你能清楚看到进化前后的差异，每一步都可追溯、可解释" |

## 重置演示

想重来一遍，点页面上的「重置状态」按钮即可。

## 常见问题

**Q: 打开页面是空的？**
A: 确认 `data/demo_state.json` 文件存在。如果丢失，从 Git 恢复：`git checkout data/demo_state.json`

**Q: pip install 报错？**
A: 确认已进入 .venv 虚拟环境（终端前有 `(.venv)` 标记）。国内用户可加镜像：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

**Q: npm install 报错？**
A: 确认 Node.js 版本 ≥ 18：`node --version`

**Q: 端口 8501 被占用？**
A: 换端口启动：`streamlit run app.py --server.port 8502`
