! demos/03_where/demo.f90
program where_demo
    implicit none
    real :: A(10)
    integer :: i

    A = [(-1.0, i=1,5), (1.0, i=6,10)]

    ! THE TRACE TARGET: WHERE block
    where (A > 0.0)
        A = A * 2.0
    elsewhere
        A = 0.0
    end where

    print *, A
end program where_demo
