class Library:
    def __init__(self):
        self.books = []

    # Add book
    def add_book(self, book):
        self.books.append(book)
        print(f'"{book}" added successfully.')

    # Show books
    def show_books(self):
        if len(self.books) == 0:
            print("No books available.")
        else:
            print("\nAvailable Books:")
            for i, book in enumerate(self.books, start=1):
                print(f"{i}. {book}")

    # Issue book
    def issue_book(self, book):
        if book in self.books:
            self.books.remove(book)
            print(f'"{book}" issued successfully.')
        else:
            print(f'"{book}" not available.')

    # Return book
    def return_book(self, book):
        self.books.append(book)
        print(f'"{book}" returned successfully.')


# Main program
library = Library()

while True:
    print("\n===== Library Menu =====")
    print("1. Add Book")
    print("2. Show Books")
    print("3. Issue Book")
    print("4. Return Book")
    print("5. Exit")

    choice = input("Enter your choice: ")

    if choice == "1":
        book = input("Enter book name: ")
        library.add_book(book)

    elif choice == "2":
        library.show_books()

    elif choice == "3":
        book = input("Enter book name to issue: ")
        library.issue_book(book)

    elif choice == "4":
        book = input("Enter book name to return: ")
        library.return_book(book)

    elif choice == "5":
        print("Thank you!")
        break

    else:
        print("Invalid choice, try again.")