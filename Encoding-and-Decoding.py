#I want encoding + decoding
st = "Mrinal is Good boy"
coding = True

# Condition 1
if coding:
    if len(st) >= 3:
        r1 = "PK"
        r2 = "MK"

        st = r1 + st[0:] + st[6] + r2
        print(st)


# Condition 2
st = input("Enter message = ")
coding = True

if coding:
    words = st.split()      # split sentence into words
    nwords = []

    for word in words:
        if len(word) >= 3:
            r1 = " "
            r2 = " "

            stnew = r1 + word[1:] + word[0] + r2
            nwords.append(stnew)

        else:
            nwords.append(word[::-1])

    print(" ".join(nwords))


# Condition 3 (reverse logic / decode)
else:
    words = st.split()
    nwords = []

    for word in words:
        if len(word) >= 3:
            stnew = word[3:-3]
            stnew = stnew[-1] + stnew[:-1]
            nwords.append(stnew)

        else:
            nwords.append(word[::-1])

    print(" ".join(nwords))