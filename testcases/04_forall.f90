! demos/04_forall/demo.f90
program forall_demo
    implicit none
    integer :: A(10, 10)
    integer :: i, j

    ! THE TRACE TARGET: FORALL
    forall (i=1:10, j=1:10)
        A(i, j) = i + j
    end forall

    print *, A(1, 1), A(10, 10)
end program forall_demo
