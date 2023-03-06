def round(n):
	return int(n * 10) / 10

for i in range(1, 14):
	x = 480 * (2 ** (i - 1))

	print()
	print("word strength: " + str(i))
	print(f"{round(x)} seconds")
	print(f'{round(x / 60 / 60)} hours')
	print(f'{round(x / 60 / 60 / 24)} days')

# displays NEXT intervals AFTER achieving that word strength
# it also takes that figure to achieve that word strength
# e.g. to achieve word word strength of 5, it takes about 2.1 hours
# AND after achieving a word strength of 5, the next interval will be about 2.1 hours