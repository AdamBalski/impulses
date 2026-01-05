funcs:
(data string)
(window stream time aggregate funcs)
(prefix stream aggrrgate func)
(lambda ...args code)
(define var val)
(filter stream predicate)
(or ...predicate)
(> num)
(< num)
(= num)
(>= num)
(<= num)
(and ...predicate)
(dimension-is dim-key dim-value)
(no-dimension dim-key)
(map stream ...funcs)
(compose stream1 stream2 ... aggregate-fn)

(* num1 num2)
(/ num1 num2)
(- num1 num2)
(+ num1 num2)
(exp num1 num2)
aggregate functions:
(aggregate-from bin-func) (e.g. *, /, +, -, exp) (returns a function that works on a group of numbers from a binary like (n1 + n2 + n3 + n4 + ... + n_I))
(p percent) returns a aggregate function of a certain percentile
(count lst) aggregate function returning count of numbrs
also other builtin aggregates would be std, min, max, sum, avg

---

## Streams mirroring `pg.py` charts

```lisp
(define deltas (data "transactions"))

(define sum (aggregate-from +))

(define expenses (filter deltas (< 0)))
(define income   (filter deltas (>= 0)))

(define acc (prefix deltas sum))

(define expenses-30d (window expenses "30d" sum))
(define income-30d   (window income "30d" sum))
(define expenses-30d-positive
  (map expenses-30d (lambda (value) (* -1 value))))

(define expenses-30d-bucket (window expenses "30d" sum))
(define income-30d-bucket   (window income "30d" sum))

(define expenses-volatility-30d
  (window expenses "30d" std))

(define savings-rate-agg
  (lambda (values)
    ((lambda (income-tot expense-tot)
       (/ (- income-tot expense-tot)
          (+ income-tot expense-tot)))
     (sum (filter values (>= 0)))
     (sum (map (filter values (< 0))
               (lambda (v) (* -1 v)))))))
(define savings-rate-30d
  (window deltas "30d" savings-rate-agg))

(define expenses-year-sum (window expenses "365d" sum))
(define expenses-year-avg
  (map expenses-year-sum (lambda (value) (/ value 365))))
(define monthly-expenses-year-avg
  (map expenses-year-avg (lambda (value) (* 30.5 value))))

(define runway
  (compose acc expenses-year-avg
       (lambda (balance avg-expense)
         (/ balance avg-expense))))
```
