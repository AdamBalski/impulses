export const COMMON_LIBRARY = `
; Duration aliases
(define MINUTE "1m")
(define HOUR "1h")
(define DAY "1d")
(define WEEK "7d")
(define MONTH "30d")
(define YEAR "365d")

; Prefix helpers
(define prefix-sum
  (lambda (series)
    (prefix series sum)))

(define prefix-count
  (lambda (series)
    (prefix series
      (aggregate-from
        (lambda (previous _next)
          (+ previous 1))))))

; Basic filters
(define positive
  (lambda (series)
    (filter series (> 0))))

(define negative
  (lambda (series)
    (filter series (< 0))))

; Scaling helpers
(define scale
  (lambda (series factor)
    (map series
         (lambda (value)
           (* value factor)))))

(define multiply
  (lambda (series factor)
    (scale series factor)))

; Window helpers
(define sum-window
  (lambda (series duration)
    (window series duration sum)))

(define count-window
  (lambda (series duration)
    (window series duration count)))

; Bucket helpers
(define buckets
  (lambda (series duration)
    (bucketize series duration sum)))

(define buckets-count
  (lambda (series duration)
    (bucketize series duration count)))

; Exponential moving average
(define ema
  (lambda (series alpha)
    (prefix series
      (aggregate-from
        (lambda (previous current)
          (+ (* alpha current)
             (* (- 1 alpha) previous)))))))
`;
