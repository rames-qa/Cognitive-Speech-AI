import time
timestamp = time.strftime('%H:%M:%S')
print(timestamp)
HOUR = int(time.strftime('%H'))
print(HOUR)
MINUTE = time.strftime('%M')
print(MINUTE)
SECOND = time.strftime('%S')
print(SECOND)
if(HOUR >= 0 and HOUR < 12):
    print("Good Morning Sir")
elif(HOUR >= 12 and HOUR < 17):
    print("Good Afternoon Sir")
else:
    print("Good Night Sir")