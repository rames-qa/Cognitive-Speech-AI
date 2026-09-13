import random
print("Game Logic (Result Matrix)")
print("User\\Computer,Snake(s),Water(w),Gun(g)")
print("Snake(s),Tie(0),Win(1),Lose(-1)")
print("Water(w),Lose (-1,Tie(0),Win(1)")
print("Gun(g),Win(1),Lose(-1),Tie(0)")
options = ["s", "w", "g"]
comp = random.choice(options)
user = input("Snake(s),Water(w),Gun(g)\nEnter (s/w/g)= ").lower()
if user not in options:
    print("Invalid input!")
else:
    print(f"\nComputer:{comp}\nYou:{user}")
    if comp == user:
        print("It's a tie!")
    elif (user == "s" and comp == "w") or \
         (user == "w" and comp == "g") or \
         (user == "g" and comp == "s"):
        print("You win!")
    else:
        print("You lose!")
