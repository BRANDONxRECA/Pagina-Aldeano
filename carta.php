<html>
    <head>
        <title>Carta</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>        
    </head>
    </head>
        <title>Restaurante "La nonna"</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
    
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    
        <link rel="stylesheet" href="style.css">
    </head>
    <body class="d-flex flex-column min-vh-100">
        <!--Navbar -->
        <nav class="navbar navbar-expand-sm bg-dark navbar-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="index.php">Logo</a>
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                    <span class="navbar-toggler-icon"></span>
                </button> 
                <div class="collapse navbar-collapse" id="collapsibleNavbar">
                    <ul class="navbar-nav">            
                        <li class="nav-item">
                            <a class="nav-link" href="carta.php">Carta</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="historial.php">Historial</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="carrito.php">Carrito</a>
                        </li>                                               
                    </ul>
                </div>  
                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#myModal">Acceder</button>                             
            </div>
        </nav>
        <!--Modal-->
        <div class="container my-5 pt-4">
            <div class="card shadow-lg mx-auto border-0 text-white" 
                style="max-width: 1100px; background-color: rgba(18, 5, 10, 0.88); backdrop-filter: blur(10px); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.1);">
                
                <div class="row g-0">
                    
                    <!-- parte isquierda -->
                    <div class="col-12 col-lg-6 p-4 border-end border-secondary border-opacity-50">
                        <h4 class="text-warning text-center border-bottom border-secondary border-opacity-50 pb-2 mb-4 fw-bold">Pastas & Entradas</h4>

                        <div class="d-flex align-items-center justify-content-between py-2 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/fideos con salsa.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Spaghetti Bolognesa&precio=7500" class="text-white text-decoration-none fw-bold link-warning">Spaghetti Bolognesa</a>
                            </div>
                            <span class="text-warning fw-bold">$7.500</span>
                        </div>

                        <div class="d-flex align-items-center justify-content-between py-2 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/fettuccine.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Fettuccine Alfredo&precio=7900" class="text-white text-decoration-none fw-bold link-warning">Fettuccine Alfredo</a>
                            </div>
                            <span class="text-warning fw-bold">$7.900</span>
                        </div>

                        <div class="d-flex align-items-center justify-content-between py-2 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/ravioles.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Ravioles de Ricotta&precio=8200" class="text-white text-decoration-none fw-bold link-warning">Ravioles de Ricotta</a>
                            </div>
                            <span class="text-warning fw-bold">$8.200</span>
                        </div>

                        <div class="d-flex align-items-center justify-content-between py-2 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/lasana.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Lasaña de Carne&precio=8500" class="text-white text-decoration-none fw-bold link-warning">Lasaña de Carne</a>
                            </div>
                            <span class="text-warning fw-bold">$8.500</span>
                        </div>

                        <div class="d-flex align-items-center justify-content-between py-2 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/ñoquis.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Ñoquis al Pesto&precio=7800" class="text-white text-decoration-none fw-bold link-warning">Ñoquis al Pesto</a>
                            </div>
                            <span class="text-warning fw-bold">$7.800</span>
                        </div>
                        <div class="d-flex align-items-center justify-content-between py-2 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/canoles.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Canelones de Espinaca&precio=8100" class="text-white text-decoration-none fw-bold link-warning">Canelones de Espinaca</a>
                            </div>
                            <span class="text-warning fw-bold">$8.100</span>
                        </div>
                        <div class="d-flex align-items-center justify-content-between py-2 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/albondigas.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Fideos con Albóndigas&precio=8400" class="text-white text-decoration-none fw-bold link-warning">Fideos con Albóndigas</a>
                            </div>
                            <span class="text-warning fw-bold">$8.400</span>
                        </div>
                        <div class="d-flex align-items-center justify-content-between py-2">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/bruschetta.jpg" class="rounded-circle me-3" style="width: 45px; height: 45px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Bruschetta Clásica&precio=4900" class="text-white text-decoration-none fw-bold link-warning">Bruschetta Clásica</a>
                            </div>
                            <span class="text-warning fw-bold">$4.900</span>
                        </div>
                    </div>

                    <!-- parte derecha-->
                    <div class="col-12 col-lg-6 p-4">
                        <h4 class="text-warning text-center border-bottom border-secondary border-opacity-50 pb-2 mb-4 fw-bold">Pizzas & Especiales</h4>
                        <div class="d-flex align-items-center justify-content-between py-3 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/p_margarita.jpg" class="rounded-circle me-3" style="width: 50px; height: 50px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Pizza Margarita&precio=9500" class="text-white text-decoration-none fw-bold fs-5 link-warning">Pizza Margarita</a>
                            </div>
                            <span class="text-warning fw-bold fs-5">$9.500</span>
                        </div>
                        <div class="d-flex align-items-center justify-content-between py-3 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/p_cuatro_q.jpg" class="rounded-circle me-3" style="width: 50px; height: 50px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Pizza Cuatro Quesos&precio=10900" class="text-white text-decoration-none fw-bold fs-5 link-warning">Pizza Cuatro Quesos</a>
                            </div>
                            <span class="text-warning fw-bold fs-5">$10.900</span>
                        </div>
                        <div class="d-flex align-items-center justify-content-between py-3 border-bottom border-secondary border-opacity-25">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/p_pepperoni.jpg" class="rounded-circle me-3" style="width: 50px; height: 50px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Pizza Pepperoni&precio=10200" class="text-white text-decoration-none fw-bold fs-5 link-warning">Pizza Pepperoni</a>
                            </div>
                            <span class="text-warning fw-bold fs-5">$10.200</span>
                        </div>
                        <div class="d-flex align-items-center justify-content-between py-3">
                            <div class="d-flex align-items-center">
                                <img src="imagenes/calzone_relleno.jpg" class="rounded-circle me-3" style="width: 50px; height: 50px; object-fit: cover;" alt="Platillo">
                                <a href="carrito.php?agregar=Calzone Relleno&precio=11500" class="text-white text-decoration-none fw-bold fs-5 link-warning">Calzone Relleno</a>
                            </div>
                            <span class="text-warning fw-bold fs-5">$11.500</span>
                        </div>

                    </div>

                </div>
            </div>
        </div>
<!--Modal Principal-->
        <div class="modal fade" id="myModal">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Autenticacion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <div class="row">
                            <!-- Izquierda: Usuario / Crear cuenta -->
                            <div class="col-sm-6 border-end">
                                <h5>Usuario</h5>
                                <form action="registro.php">
                                    <div class="mb-3 mt-3">
                                        <label for="emailUser" class="form-label">Email:</label>
                                        <input type="email" class="form-control" id="emailUser" placeholder="Enter email" name="email">
                                    </div>
                                    <button type="submit" class="btn btn-primary mb-3">Crear cuenta</button>
                                </form>
                                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#loginModal">Iniciar sesion</button>
                            </div>

                            <!-- Derecha: Trabajadores -->
                            <div class="col-sm-6">
                                <h5>Trabajadores</h5>
                                <form action="trabajador.php">
                                    <div class="mb-3 mt-3">
                                        <label for="emailTrab" class="form-label">Email:</label>
                                        <input type="email" class="form-control" id="emailTrab" placeholder="Enter email" name="email">
                                    </div>
                                    <div class="mb-3">
                                        <label for="pwdTrab" class="form-label">Password:</label>
                                        <input type="password" class="form-control" id="pwdTrab" placeholder="Enter password" name="pswd">
                                    </div>
                                    <button type="submit" class="btn btn-primary">Login</button>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>

        <!--Modal Inicio Sesion Usuario-->
        <div class="modal fade" id="loginModal">
            <div class="modal-dialog">
                <div class="modal-content">
                    <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Inicio de sesion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <form action="empresa.php">
                            <div class="mb-3 mt-3">
                                <label for="email" class="form-label">Email:</label>
                                <input type="email" class="form-control" id="email" placeholder="Enter email" name="email">
                            </div>
                            <div class="mb-3">
                                <label for="pwd" class="form-label">Password:</label>
                                <input type="password" class="form-control" id="pwd" placeholder="Enter password" name="pswd">
                            </div>
                            <div class="form-check mb-3">
                                <label class="form-check-label">
                                    <input class="form-check-input" type="checkbox" name="remember"> Remember me
                                </label>
                            </div>
                            <button type="submit" class="btn btn-primary">Login</button>
                        </form>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-toggle="modal" data-bs-target="#myModal">Volver</button>
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        </div>
</html>