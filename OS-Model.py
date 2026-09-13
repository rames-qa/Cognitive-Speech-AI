import os
os.makedirs("data", exist_ok=True)
for i in range(1, 101):
    folder_name = f"data/Day{i}"
    os.makedirs(folder_name, exist_ok=True)
    file_path = f"{folder_name}/task.txt"
    with open(file_path, "w") as file:
        file.write(f"Day {i} Work\n")
        file.write("Topic: Python Practice\n")
        file.write("Task: Complete coding exercises\n")
        file.write("Status: Pending\n")
print("100 folders with task files created!")