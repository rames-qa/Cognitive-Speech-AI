# Open file in read mode
f = open("myfile.text", "r")

# Read file line by line
while True:
    line = f.readline()

    # Stop when file ends
    if not line:
        break

    # Print each line
    print(line, end="")

# Close file
f.close()