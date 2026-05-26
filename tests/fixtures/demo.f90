! demo.f90
! Basic Fortran fixture for testing Flang stage dumps

program main
  implicit none
  integer :: i, sum
  integer, dimension(10) :: arr

  ! 1. Simple initialization
  sum = 0

  ! 2. Array operations
  arr = [(i, i=1,10)]

  ! 3. Do Concurrent loop
  do concurrent (i=1:10)
    arr(i) = arr(i) * 2
  end do

  ! 4. Reduction/computation
  do i = 1, 10
    sum = sum + arr(i)
  end do

  print *, "Sum is: ", sum

end program main
