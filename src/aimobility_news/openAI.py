from openai import OpenAI

client = OpenAI()

models = client.models.list()

for model in models.data:
    if "gpt-6" in model.id:
        print(model.id)