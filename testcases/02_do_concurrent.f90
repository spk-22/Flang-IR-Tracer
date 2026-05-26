! demos/02_do_concurrent/demo.f90
program do_concurrent_demo
    implicit none
    integer, parameter :: N = 100
    real :: A(N), B(N)
    integer :: i

    B = 1.0

    ! THE TRACE TARGET: DO CONCURRENT
    do concurrent (i=1:N)
        A(i) = B(i) * 2.0
    end do

    print *, A(1), A(N)
end program do_concurrent_demo
