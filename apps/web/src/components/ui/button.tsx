import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "../../lib/utils";

// 48px touch targets on phones; denser from md (tablet/desktop).
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-brand text-brand-ink shadow-[inset_0_1px_0_rgb(255_255_255/0.12)] hover:bg-brand-strong",
        secondary: "border border-line bg-surface text-ink shadow-card hover:border-line-strong hover:bg-subtle/60",
        ghost: "text-ink-2 hover:bg-subtle hover:text-ink",
        soft: "bg-brand-soft text-brand-strong hover:bg-brand-soft/70",
      },
      size: {
        sm: "min-h-10 px-3 text-sm md:min-h-8",
        md: "min-h-12 px-4 text-base md:min-h-10 md:text-[0.95rem]",
        lg: "min-h-12 px-5 text-base md:min-h-12",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
  },
);
Button.displayName = "Button";
