f = open("myfile.text", "w")
f.write("Hi am from bangalore\n")
f.write("I am Medical Electronics Engineer")
f.close()

f = open("myfile.text", "r")
print(f.read())
f.close()