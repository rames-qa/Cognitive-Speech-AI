class Person:
    def __init__(self, name):
        self.__name = name

    def get_name(self):
        return self.__name

    def set_name(self, new_name):
        if isinstance(new_name, str):
            self.__name = new_name
        else:
            print("Name must be string")


p = Person("Ramesh")
p.set_name(123)      # invalid
print(p.get_name())