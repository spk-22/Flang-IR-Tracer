! demos/08_elemental/demo.f90
program elemental_demo
    implicit none
    real :: A(5), B(5)

    A = [1.0, 4.0, 9.0, 16.0, 25.0]

    ! THE TRACE TARGET: Elemental function call
    B = sqrt(A)

    print *, B
end program elemental_demo
