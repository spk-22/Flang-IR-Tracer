! demos/05_poly_dispatch/demo.f90
module shapes
    type, abstract :: shape
    contains
        procedure(area_interface), deferred :: area
    end type shape

    abstract interface
        function area_interface(self)
            import :: shape
            real :: area_interface
            class(shape), intent(in) :: self
        end function
    end interface

    type, extends(shape) :: square
        real :: side
    contains
        procedure :: area => square_area
    end type square

contains
    function square_area(self)
        class(square), intent(in) :: self
        real :: square_area
        square_area = self%side * self%side
    end function
end module shapes

program poly_demo
    use shapes
    implicit none
    class(shape), allocatable :: s
    real :: a

    allocate(square :: s)
    select type (s)
        type is (square)
            s%side = 10.0
    end select

    ! THE TRACE TARGET: Polymorphic dispatch
    a = s%area()

    print *, "Area: ", a
end program poly_demo
