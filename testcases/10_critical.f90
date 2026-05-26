! demos/10_critical/demo.f90
program critical_demo
    implicit none
    integer :: shared_var

    shared_var = 0

    ! THE TRACE TARGET: CRITICAL section
    critical
        shared_var = shared_var + 1
    end critical

    print *, shared_var
end program critical_demo
