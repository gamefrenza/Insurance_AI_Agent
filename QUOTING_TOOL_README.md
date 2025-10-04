# Advanced Insurance Quoting Tool

## 概述

`quoting_tool.py` 是一个基于 LangChain 构建的专业保险报价工具，支持汽车保险和健康保险的自动化报价计算。

## 主要特性

### ✅ 功能特点

1. **完整的数据验证** - 使用 Pydantic V2 模型进行严格的数据验证
2. **预定义费率表** - 包含汽车和健康保险的详细费率计算规则
3. **外部API集成** - 模拟 Guidewire 保险系统的 API 调用
4. **异步支持** - 支持同步和异步两种调用方式
5. **详细报价单** - 生成包含所有细节的专业报价文档
6. **错误处理** - 完善的错误处理和用户友好的错误提示

### 📊 支持的保险类型

#### 1. 汽车保险 (Auto Insurance)

**费率计算公式:**
```
总保费 = 基础保费 × 年龄因子 × 地点因子 × 车辆价值因子 × 其他因子
```

**因子说明:**
- **基础保费**: $1,000/月
- **年龄因子**:
  - < 25 岁: 1.20x (高风险)
  - 25-65 岁: 1.00x (标准)
  - > 65 岁: 1.15x (中等风险)
- **地点因子**:
  - 城市 (urban): 1.10x
  - 郊区 (suburban): 1.00x
  - 乡村 (rural): 0.90x
- **车辆价值因子**:
  - < $20,000: 1.00x
  - $20,000-$40,000: 1.15x
  - $40,000-$60,000: 1.30x
  - $60,000-$100,000: 1.50x
  - > $100,000: 1.80x
- **其他因子**:
  - 商业用途: +20%
  - 新车 (< 5年): -5%
  - 旧车 (> 15年): +10%
  - 年轻男性 (< 25岁): +10%

**覆盖范围:**
- 责任险: $100,000
- 碰撞险: $50,000
- 综合险: $50,000
- 医疗支付: $10,000
- 未保险驾驶人: $50,000
- **免赔额**: $1,000

#### 2. 健康保险 (Health Insurance)

**费率计算公式:**
```
总保费 = 基础保费 × 年龄因子 × 地点因子 × 健康因子
```

**因子说明:**
- **基础保费**: $500/月
- **年龄因子**:
  - < 25 岁: 0.85x (较低风险)
  - 25-65 岁: 1.00x (标准)
  - > 65 岁: 1.50x (高风险)
- **地点因子**: 同汽车保险
- **健康因子**:
  - 吸烟者: 1.30x
  - 既往病史: 1.25x
  - 高 BMI (> 30): 1.15x
  - 低 BMI (< 18.5): 1.10x
  - 不运动: 1.10x
  - 经常运动: 0.95x (折扣)

**覆盖范围:**
- 年度最高额: $1,000,000
- 预防性护理: 100% 覆盖
- 急诊室: 自付额后 80%
- 处方药: 有共付额的覆盖
- 住院: 自付额后 80%
- **免赔额**: $2,500

## 安装依赖

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 独立使用工具

```python
from quoting_tool import QuotingTool
import json

# 创建工具实例
tool = QuotingTool()

# 准备客户数据
customer_data = {
    "age": 30,
    "gender": "male",
    "address": "123 Main St, New York, NY",
    "location_type": "urban",
    "insurance_type": "auto",
    "vehicle_details": {
        "make": "Tesla",
        "model": "Model 3",
        "year": 2022,
        "value": 45000,
        "usage": "personal"
    }
}

# 生成报价
quote = tool._run(json.dumps(customer_data))
print(quote)
```

### 2. 集成到 LangChain Agent

```python
from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI
from quoting_tool import QuotingTool

# 初始化 LLM
llm = ChatOpenAI(model="gpt-4", temperature=0.2)

# 创建工具列表
tools = [QuotingTool()]

# 初始化 agent
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# 使用自然语言查询
response = agent.invoke({
    "input": "Calculate auto insurance for a 25-year-old with a BMW X5 in Chicago"
})
```

### 3. 异步使用

```python
import asyncio
from quoting_tool import QuotingTool
import json

tool = QuotingTool()

async def get_quote():
    customer_data = {
        "age": 35,
        "gender": "female",
        "address": "456 Elm St, Los Angeles, CA",
        "location_type": "suburban",
        "insurance_type": "health",
        "health_details": {
            "smoker": False,
            "pre_existing_conditions": False,
            "bmi": 23.5,
            "exercise_frequency": "regular"
        }
    }
    
    quote = await tool._arun(json.dumps(customer_data))
    print(quote)

asyncio.run(get_quote())
```

## 输入数据格式

### 汽车保险输入示例

```json
{
  "age": 30,
  "gender": "male",
  "address": "123 Main Street, New York, NY 10001",
  "location_type": "urban",
  "insurance_type": "auto",
  "vehicle_details": {
    "make": "Tesla",
    "model": "Model 3",
    "year": 2022,
    "value": 45000,
    "usage": "personal"
  }
}
```

### 健康保险输入示例

```json
{
  "age": 35,
  "gender": "female",
  "address": "456 Elm Street, Los Angeles, CA 90001",
  "location_type": "suburban",
  "insurance_type": "health",
  "health_details": {
    "smoker": false,
    "pre_existing_conditions": false,
    "bmi": 24.5,
    "exercise_frequency": "regular"
  }
}
```

## 字段说明

### 必填字段（所有保险类型）

| 字段 | 类型 | 说明 | 有效值 |
|------|------|------|--------|
| age | integer | 客户年龄 | 18-100 |
| gender | string | 性别 | male, female, other |
| address | string | 地址 | 至少 5 个字符 |
| location_type | string | 地点类型 | urban, suburban, rural |
| insurance_type | string | 保险类型 | auto, health |

### 汽车保险特定字段 (vehicle_details)

| 字段 | 类型 | 说明 | 有效值 |
|------|------|------|--------|
| make | string | 制造商 | 非空 |
| model | string | 型号 | 非空 |
| year | integer | 年份 | 1990-2026 |
| value | float | 车辆价值 (USD) | >= 0 |
| usage | string | 用途 (可选) | personal, commercial |

### 健康保险特定字段 (health_details)

| 字段 | 类型 | 说明 | 有效值 |
|------|------|------|--------|
| smoker | boolean | 是否吸烟 | true, false |
| pre_existing_conditions | boolean | 是否有既往病史 | true, false |
| bmi | float | 体重指数 (可选) | 10-60 |
| exercise_frequency | string | 运动频率 (可选) | none, occasional, regular, frequent |

## 示例程序

### 运行内置示例

```bash
# 运行工具的独立示例
python quoting_tool.py

# 运行集成示例
python example_advanced_quoting.py
```

### 可用示例

1. **直接工具使用** - 不使用 agent，直接调用工具
2. **Agent 集成** - 与 LangChain agent 集成使用
3. **结构化输入** - 程序化构建输入数据
4. **批量报价** - 批量生成多个报价
5. **错误场景** - 演示错误处理
6. **异步使用** - 异步并发生成报价

## API 集成

工具包含了外部 API 集成的模拟实现（模拟 Guidewire 系统）。

### 在生产环境中使用

要连接真实的 API，修改 `InsuranceAPIClient` 类：

```python
class InsuranceAPIClient:
    API_ENDPOINT = "https://your-insurance-api.com/v1/quotes"
    API_KEY = "your-api-key"
    
    @classmethod
    def submit_quote(cls, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            cls.API_ENDPOINT,
            json=quote_data,
            timeout=10,
            headers={"Authorization": f"Bearer {cls.API_KEY}"}
        )
        response.raise_for_status()
        return response.json()
```

## 错误处理

工具提供了完善的错误处理：

1. **数据验证错误** - 详细的字段验证和错误提示
2. **JSON 解析错误** - 友好的格式错误提示
3. **API 错误** - API 调用失败时的后备机制
4. **类型错误** - 严格的类型检查和转换

## 输出格式

工具生成的报价单包含：

- 报价 ID 和时间戳
- 客户信息
- 保费计算明细（基础保费、各类因子）
- 月度和年度总保费
- 覆盖范围详情
- 免赔额
- 保单有效期
- API 集成状态
- 重要说明和下一步骤

## 技术架构

```
quoting_tool.py
├── Pydantic Models (数据验证)
│   ├── CustomerData
│   ├── VehicleDetails
│   ├── HealthDetails
│   └── QuoteResult
├── Rate Tables (费率表)
│   ├── BASE_RATES
│   ├── AGE_FACTORS
│   ├── LOCATION_FACTORS
│   └── HEALTH_FACTORS
├── API Client (外部集成)
│   ├── submit_quote()
│   └── submit_quote_async()
├── Premium Calculator (保费计算)
│   ├── calculate_auto_insurance()
│   └── calculate_health_insurance()
└── QuotingTool (主工具类)
    ├── _run() - 同步执行
    ├── _arun() - 异步执行
    └── _format_quote_response()
```

## 与现有系统集成

可以轻松集成到现有的 `insurance_agent.py` 中：

```python
from insurance_agent import InsuranceAgent
from quoting_tool import QuotingTool

# 替换或添加高级报价工具
agent = InsuranceAgent()
agent.tools.append(QuotingTool())
```

## 最佳实践

1. **数据验证** - 在调用工具前验证所有必需字段
2. **错误处理** - 始终捕获和处理潜在的错误
3. **日志记录** - 工具自动记录所有重要操作
4. **异步使用** - 在需要并发处理时使用异步版本
5. **API 密钥** - 在生产环境中安全存储 API 密钥

## 合规性

- **GDPR 合规** - 所有数据处理符合 GDPR 标准
- **数据加密** - 敏感数据传输加密
- **隐私保护** - 最小化数据收集和存储
- **审计日志** - 完整的操作日志记录

## 许可证

与主项目相同的许可证。

## 支持

如有问题或建议，请参考主项目的 README.md 或提交 issue。

---

**注意**: 这是一个演示工具，费率表和计算公式仅供示例使用。实际生产环境中应使用精算师认证的费率表。

