!mod$ v1 sum:eb6c2f5de63184e2
module shapes
type,abstract::shape
contains
procedure(area_interface),deferred::area
end type
abstract interface
function area_interface(self)
import::shape
class(shape),intent(in)::self
real(4)::area_interface
end
end interface
type,extends(shape)::square
real(4)::side
contains
procedure::area=>square_area
end type
contains
function square_area(self)
class(square),intent(in)::self
real(4)::square_area
end
end
