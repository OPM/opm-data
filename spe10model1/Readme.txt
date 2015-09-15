The SPE paper suggested that Qinj=0.2641 Mscf/d.
Nevertheless it is impossible to get results matching those of the SPE paper.
After few different tries, a value of Qinj=34.61 Mscf/d seems to give staisfying results.
If Qinj=0.2461 Mscf/d, tuning is not necessary
If Qinj=34.61 Mscf/d, the param file should be used for the Flow run.

Qinj=34.61 Mscf/d is the implemented value.

Few changes:
- TABDIMS item 3 has been increased to use only one SGOF table
- PVDO & PVDG contained more constraining data to ensure simulating uncompressible fluids.
- Timestep in the data file is limited to 10 days to avoid convergence issues
- It takes about 1 min to run the simulation on eclipse and about 1 hour with Flow
