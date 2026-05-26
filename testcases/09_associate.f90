! demos/09_associate/demo.f90
program associate_demo
    implicit none
    real :: x, y, z

    x = 1.0; y = 2.0; z = 3.0

    ! THE TRACE TARGET: ASSOCIATE construct
    associate (val => x + y + z)
        print *, val * 2.0
    end associate

end program associate_demo
