import openai
import json
import re

OPENAI_API_KEY =  os.environ.get("OPENAI_API_KEY")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def recommend_chart_and_fields(schema, sample_rows):
    """
    schema: dict, e.g. {"city": "object", "score": "float64", ...}
    sample_rows: list of dict, e.g. [{"city": "Beijing", "score": 4.5, ...}, ...]
    """
    prompt = f'''
    You are a data visualization assistant. Given the following table schema and sample data, please recommend the most suitable chart type (bar/line/pie/scatter, etc.) and the best X and Y fields, and briefly explain your reasoning.
    Field types: {schema}
    Sample data: {sample_rows[:3]}
    Please answer in the following JSON format: {{"chart_type": "...", "x_field": "...", "y_field": "...", "reason": "..."}}.
    Note: x_field and y_field must be strictly filled in as column names (such as "longitude", "latitude"), do not fill in specific values (such as 25.8092, -80.24)! Only use column names!
    The reason field should be a brief explanation in English.
    The chart_type must be one of: bar, line, pie, scatter.
    '''
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300
        )
        text = response.choices[0].message.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                result["raw_reply"] = text
                return result
            except Exception:
                return {"raw_reply": text}
        return {"raw_reply": text}
    except Exception as e:
        print("OpenAI API call failed:", e)
        return {"raw_reply": f"OpenAI API call failed: {e}"}

def summarize_csv_with_openai(schema, sample_rows):
    """
    用OpenAI对CSV结构和样例数据进行英文归纳分析，返回简明summary。
    """
    prompt = f'''
    You are a data analyst. Please summarize the following CSV file in English.
    1. Briefly describe the main fields and their types.
    2. Summarize the main content and any obvious trends or highlights.
    3. If possible, mention what kind of chart or analysis is suitable for this data.
    Here is the CSV schema: {schema}
    Sample data: {sample_rows[:3]}
    Please answer in 3-5 sentences in English.
    '''
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300
        )
        text = response.choices[0].message.content.strip()
        return text
    except Exception as e:
        print("OpenAI summary API call failed:", e)
        return f"OpenAI summary API call failed: {e}"; 