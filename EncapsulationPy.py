class Animal:
    def sound(self):
        print("some sound")
    
    def sleep(self):
        print("Animal is sleeping ")
class Dog(Animal):
    def sound(self):
        print("Barking")

    def sleep(self):
        print("Dog is sleeping")
d=Dog()
d.sound()
d.sleep()
