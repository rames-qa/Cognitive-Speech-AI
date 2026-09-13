import time
timestamp= time.strftime('%H:%M:%S')
print(timestamp)
HOUR=int(time.strftime('%H'))
MINUTE=time.strftime('%M')
SECOND=time.strftime('%S')
print(HOUR)
print(MINUTE)
print(SECOND)
if HOUR < 12:
    print("Good Morning")
elif HOUR < 17:
    print("Good Afternoon")
else:
    print("Good Evening")