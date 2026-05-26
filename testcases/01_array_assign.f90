! demos/01_array_assign/demo.f90
program array_assign
    implicit none
    integer, parameter :: N = 100
    real :: A(N), B(N), C(N)
    integer :: i

    ! Initialize
    do i = 1, N
        B(i) = float(i)
        C(i) = float(i * 2)
    end do

    ! THE TRACE TARGET: Whole-array assignment
    ! This should lower to hlfir.assign and hlfir.elemental
    A(:) = B(:) + C(:)

    print *, A(1), A(N)
end program array_assign
