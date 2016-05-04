""" Code from http://habrahabr.ru/post/259095/"""

def is_prime(n):
   if not n % 2:
      return False
   i = 3
   while True:
      if n % i == 0:
          return False
      i += 2
      if i >= n:
          return True
   return True

def sexy_primes(n):
   l = []
   for j in range(9, n+1):
      if is_prime(j-6) and is_prime(j):
         l.append([j-6, j])
   return l
