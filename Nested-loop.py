# Take input as STRING
name = input("Enter a name= ")

# Loop through each character
for i in name:
    print(i)
    if i == "b":
        print("This is something Special!")

print("\n--- Names List ---")

names = ["Swapna", "Mrinal", "Guhanap", "Ramesh"]

for name in names:
    print("\nName:", name)
    
    for ch in name:
        print(ch)
    
    # Small loop (safe)
    for k in range(5):
        print(k + 1)

# Separate large loop (not inside others)
print("\n--- Large Loop ---")
for k in range(1, 21):   # reduced from 20000 to 20
    print(k)

print("\n--- Step Loop ---")
for k in range(1, 12, 3):
    print(k)