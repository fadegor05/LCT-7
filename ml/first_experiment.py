from ultralytics import YOLOE
import torch
from PIL import Image
import json, time, argparse
from pathlib import Path

device = "cuda" if torch.cuda.is_available() else "cpu"
print(device)

im_path = Path("data/raw/dataset/images/Строительная_техника/Screenshot_26.png")
prompt_path = Path("configs/prompt.json")

image = Image.open(im_path).convert("RGB")

model = YOLOE("yoloe-26s-seg.pt")

with open(prompt_path, 'r', encoding='utf-8') as file:
    mapping = json.load(file)

prompts = list(mapping.keys())

embeddings = model.get_text_pe(prompts)
model.set_classes(prompts, embeddings)

result = model(image, device=device, conf=0.05, imgsz=640)

boxes = result[0].boxes 

if len(boxes) != 0:
    for cls_id, conf, xyxy in zip(boxes.cls.tolist(), boxes.conf.tolist(), boxes.xyxy.tolist()):
        name = result[0].names[int(cls_id)]
        in_class = mapping[name]

        print(f"Имя: {name}")
        print(f"Наш класс: {in_class}")
        print(f"Conf: {conf}")
        print(f"Позиция: {xyxy}")

    annotated = result[0].plot(masks=False)
    result[0].show()
else:
    print("Модель ничего не нашла")

