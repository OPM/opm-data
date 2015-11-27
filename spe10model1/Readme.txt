This is the script of the SPE10MODEL1 case.

In previous versio, wrong values of Bg were entered (units problem), correct value is 178.1076.
- TABDIMS item 3 has been increased to use only one SGOF table
- PVDO & PVDG contained more constraining data to ensure simulating uncompressible fluids.
- Timestep in the data file is limited to 10 days to avoid convergence issues (50 day timestep do not run on Flow)
- It takes about 1 min to run the simulation on eclipse and about 1 week with Flow
