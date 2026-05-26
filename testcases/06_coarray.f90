! demos/06_coarray/demo.f90
program coarray_demo
    implicit none
    integer :: A[*]
    integer :: val

    ! THE TRACE TARGET: Coarray access
    A = 10
    val = A[1]

    print *, val
end program coarray_demo
