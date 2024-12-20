# Race Predictor Model

XGBoost-based race prediction model based on data from [this study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5000509/)

## Notes on unclear columns

- not sure what the cohort columns represent; study authors refer to all participants as a single cohort
- endurancespeed: participants rated themselves from endurance runner (1) to speed demon (10); I think this is that?
- endurancecat: no idea
- footwear: 2=normal, 1=minimalist, 0=vibrams/sandals/barefoot
- group: no idea
- xx_d: race distance
- xx_di: race difficulty (5=Very hilly, hot, or windy, 4=Hilly, hot, or windy, 3=average, 2=Cool, calm, and flat, 1=Downhill or tailwind)
- xx_tr: training at race (As fit as I’ve ever been/Good shape, but I could have trained a bit harder/I’d trained some/I wasn’t well prepared) - unsure of direction!
- typical: typical weekly mileage
- max: max weekly mileage
- sprint: whether did "sprints, intervals, or hill repeats" most weeks (so vague!)
- tempo: whether did tempo runs most weeks
