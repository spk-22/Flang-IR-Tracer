! demos/07_slice/demo.f90
program slice_demo
    implicit none
    integer :: A(10, 10), B(5, 5)
    integer :: i, j

    do i = 1, 10
        do j = 1, 10
            A(i, j) = i * 10 + j
        end do
    end do

    ! THE TRACE TARGET: Array section slicing
    B = A(1:10:2, 1:10:2)

    print *, B(1, 1), B(5, 5)
end program slice_demo
