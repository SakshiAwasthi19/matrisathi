import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../lib/utils";

// 48px touch targets on phones; slightly denser from md (tablet/desktop).
const buttonVariants = cva(
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-md px-4 text-base font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50 md:min-h-10",
  {
    variants: {
      variant: {
        primary: "bg-brand text-brand-ink hover:bg-brand-strong",
        secondary: "border border-line bg-surface text-ink hover:bg-subtle",
        ghost: "text-ink hover:bg-subtle",
      },
    },
    defaultVariants: { variant: "primary" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp ref={ref} className={cn(buttonVariants({ variant }), className)} {...props} />;
  },
);
Button.displayName = "Button";
